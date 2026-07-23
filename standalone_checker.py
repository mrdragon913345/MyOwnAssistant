import asyncio
import time
import os
import re
import sys
import itertools
import random
import subprocess

# Ensure we can import from the bot's codebase
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shopi_api import prewarm_site_for_checkout, check_shopify_card
from bot.handlers.shopify_cmds import parse_and_convert_to_usd, _SITE_ERROR_INDICATORS, _DECLINE_INDICATORS

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

async def run_checkout_mode(with_cc=False):
    print(f"=== Shopify Standalone Checkout Checker ({'WITH CC' if with_cc else 'NO CC'}) ===")
    
    # 1. Load sites
    sites_file = "sites.txt"
    if not os.path.exists(sites_file):
        print(f"Please create {sites_file} with a list of shopify urls (one per line).")
        input("Press Enter to continue...")
        return
        
    with open(sites_file, "r") as f:
        custom_sites = [line.strip() for line in f if line.strip()]
        
    if not custom_sites:
        print("No sites found in sites.txt")
        input("Press Enter to continue...")
        return
        
    # 2. Load proxies
    proxies_file = "proxies.txt"
    proxies = []
    if os.path.exists(proxies_file):
        with open(proxies_file, "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
    
    if not proxies:
        print("Warning: No proxies found in proxies.txt, running proxyless...")
    else:
        print(f"Loaded {len(proxies)} proxies.")
        
    # 3. Setup CC Mode
    test_cc = None
    if with_cc:
        test_cc = input("Enter CC (CC|MM|YYYY|CVV): ").strip()
        if not test_cc:
            print("No CC entered. Aborting.")
            input("Press Enter to continue...")
            return
        
    is_check_only = not bool(test_cc)
    normalized_cards = [test_cc] if test_cc else ["4012888888881881|12|2030|123"]
    
    # 4. Prewarm
    print(f"\n🔍 Pre-warming and checking {len(custom_sites)} Shopify sites...")
    sem_size = min(100, max(20, len(proxies) if proxies else 20))
    sem = asyncio.Semaphore(sem_size)
    
    async def sem_prewarm(site):
        async with sem:
            return await prewarm_site_for_checkout(site, proxies, max_retries=2)

    start_time = time.time()
    prewarm_tasks = [sem_prewarm(site) for site in custom_sites]
    prewarm_results = await asyncio.gather(*prewarm_tasks)
    
    alive_sites = []
    site_prices = {}
    for res in prewarm_results:
        if res['status'] == 'alive':
            alive_sites.append(res['site'])
            site_prices[res['site']] = {
                'price': res.get('price'),
                'currency': res.get('currency') or 'USD'
            }

    if not alive_sites:
        print("❌ No Shopify sites responded as 'alive'.")
        input("Press Enter to continue...")
        return

    if is_check_only:
        print(f"🔋 Pre-warm complete: {len(alive_sites)} alive sites.\nFetching exact shipping costs (No-CC Mode)...")
    else:
        print(f"🔋 Pre-warm complete: {len(alive_sites)} alive sites.\nChecking card {normalized_cards[0]}...")

    # 5. Check
    card_cycle = itertools.cycle(normalized_cards)

    async def sem_check(initial_site, c_line):
        async with sem:
            site = initial_site
            for attempt in range(3):
                res = await check_shopify_card(c_line, site, random.choice(proxies) if proxies else '', check_only=is_check_only, uid=None)
                if not res.get('retry'):
                    return res
                if attempt < 2:
                    site = random.choice(alive_sites)
                    await asyncio.sleep(1)
            return res

    tasks = [sem_check(site, next(card_cycle)) for site in alive_sites]
    results = await asyncio.gather(*tasks)
    elapsed = round(time.time() - start_time, 2)

    # 6. Classify
    under_10_lines = []
    under_20_lines = []
    above_20_lines = []
    dead_lines = []
    site_error_lines = []

    for res, site in zip(results, alive_sites):
        status = res.get('status', 'Dead')
        message = res.get('message', 'Declined')
        gw = res.get('gateway', 'shopify')
        
        msg_lower = message.lower()
        if 'non_shopify_gateway' in msg_lower or 'dynamic_pricing_unsupported' in msg_lower:
            status = "Dead"
            message = f"Non-Shopify Gateway ({gw})" if gw and gw.lower() not in ['unknown', 'shopify', ''] else "Non-Shopify Gateway"

        if status == 'Dead' and any(ind in message.lower() for ind in _SITE_ERROR_INDICATORS):
            status = 'Site Error'
            
        p_val = str(res.get('price', '-'))
        api_currency = res.get('Currency') or res.get('currency') or 'USD'
        
        if p_val == '-' or p_val == '0.00':
            is_accurate_price = False
            p_val = '-'
        else:
            is_accurate_price = 'Ship:' in p_val or 'Tax:' in p_val
            if not re.match(r'^[A-Za-z£€$₹¥]', p_val):
                p_val = f"{api_currency} {p_val}"

        price_float, price_display = parse_and_convert_to_usd(p_val)
        price_product_float, _ = parse_and_convert_to_usd(p_val, extract_product_price=True)
        bucket_price = price_product_float if price_product_float > 0.0 else price_float
        
        if not is_accurate_price:
            prewarm_info = site_prices.get(site, {})
            prewarm_price_str = prewarm_info.get('price')
            if prewarm_price_str:
                try:
                    prewarm_float = float(str(prewarm_price_str).replace('$', '').replace(' ', '').strip())
                    if prewarm_float > bucket_price:
                        bucket_price = prewarm_float
                        price_display = f"${prewarm_float:.2f} (+ Unknown Ship)"
                except:
                    pass

        line_str = f"Site: {site} | GW: {gw} | Price: {price_display} | Status: {status} | Response: {message}"

        is_success_check = (status in ['Charged', 'Approved', '3DS', 'Alive']) or (status == 'Dead' and any(ind in message.lower() for ind in _DECLINE_INDICATORS))
        is_site_error = (status == 'Site Error') or any(ind in message.lower() for ind in _SITE_ERROR_INDICATORS)
        
        if "dynamic_pricing_unsupported" in message.lower() or "dynamic pricing unsupported" in message.lower() or "non_shopify_gateway" in message.lower():
            is_success_check = False
            is_site_error = False

        if is_site_error:
            dead_lines.append(line_str + " [SITE ERROR: needs fixing]")
            site_error_lines.append(line_str)
        elif not is_success_check:
            dead_lines.append(line_str)
        elif not is_accurate_price:
            above_20_lines.append(line_str + " [Price Not 100% Accurate - Missing Shipping]")
        elif bucket_price > 20.0:
            above_20_lines.append(line_str)
        elif bucket_price > 10.0:
            under_20_lines.append(line_str)
        else:
            under_10_lines.append(line_str)

    # 7. Print Results
    print("\n" + "="*40)
    print("🛒 CHECKOUT DONE" if test_cc else "🔍 SITE CHECK DONE")
    print("="*40)
    print(f"🌐 Sites Checked: {len(alive_sites)}")
    print(f"🟢 Below $10:     {len(under_10_lines)}")
    print(f"🟡 Below $20:     {len(under_20_lines)}")
    print(f"🔴 Above $20:     {len(above_20_lines)}")
    print(f"⚙️ Site Errors:   {len(site_error_lines)}")
    print(f"💀 Dead:          {len(dead_lines) - len(site_error_lines)}")
    print(f"⏱ Time Taken:    {elapsed}s")
    print("="*40)
    
    os.makedirs("results", exist_ok=True)
    def save_res(lines, name):
        if lines:
            with open(f"results/{name}.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print(f"Saved {len(lines)} sites to results/{name}.txt")
            
    save_res(under_10_lines, "below_10")
    save_res(under_20_lines, "below_20")
    save_res(above_20_lines, "above_20")
    save_res(dead_lines, "dead_sites")
    input("\nPress Enter to return to menu...")

def run_site_checker_api():
    clear_screen()
    print("=== Site Checker API Validation ===")
    print("This mode calls site_checker_api.py (Requires local Flask API running on port 5000)")
    
    sites_file = "sites.txt"
    if not os.path.exists(sites_file):
        print(f"Please create {sites_file} with a list of shopify urls (one per line).")
        input("Press Enter to continue...")
        return
        
    threads = input("Enter number of threads [default: 10]: ").strip()
    if not threads:
        threads = "10"
        
    proxies_file = "proxies.txt"
    proxy_arg = ""
    if os.path.exists(proxies_file):
        with open(proxies_file, "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
            if proxies:
                print(f"Found {len(proxies)} proxies in proxies.txt. Using the first one as default proxy.")
                proxy_arg = f"--proxy {proxies[0]}"
                
    cmd = f"python site_checker_api.py --sites-file sites.txt --threads {threads} {proxy_arg}"
    print(f"\nRunning: {cmd}\n")
    try:
        subprocess.run(cmd, shell=True)
    except Exception as e:
        print(f"Error executing site checker: {e}")
        
    input("\nPress Enter to return to menu...")

async def main():
    while True:
        clear_screen()
        print("="*40)
        print("    SHOPIद्योगिक STANDALONE TOOLKIT")
        print("="*40)
        print("1. Find Live Sites & Price Buckets (NO CC)")
        print("2. Find Live Sites & Price Buckets (WITH CC)")
        print("3. Validate Sites against Gateways (Site Checker API Mode)")
        print("4. Exit")
        print("="*40)
        
        choice = input("Select an option: ").strip()
        
        if choice == '1':
            clear_screen()
            await run_checkout_mode(with_cc=False)
        elif choice == '2':
            clear_screen()
            await run_checkout_mode(with_cc=True)
        elif choice == '3':
            run_site_checker_api()
        elif choice == '4':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Try again.")
            time.sleep(1)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
