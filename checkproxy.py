import threading
import queue
import requests
import typing
import time
import sys
import random
import os

try:
    import rich
    import rich.progress
    import rich.progress_bar
except ImportError:
    print("This proxy checker requires the rich library to work.\nTry pip3 install rich .")
    exit(1)

CHECK_TIMEOUT_SECONDS = 1
TEST_URLS = [
    "https://httpbin.org/ip",
    "https://api.ipify.org",
    "https://api.ipify.org?format=json",
    "https://ipinfo.io"
]

class Proxy:
    def __init__(self, protocol: str, address: str) -> None:
        self.protocol = protocol
        self.address = address
        self.ip = address.split(":")[0]
        self.port = int(address.split(":")[1])
        self.link = f"{protocol}://{address}"


def check_socks() -> bool:
    try:
        requests.get(
            "https://httpbin.org/ip",
            proxies={"https": "socks5://justatest.com"},
            timeout=CHECK_TIMEOUT_SECONDS,
        )
    except Exception as e:
        return e.args[0] != "Missing dependencies for SOCKS support."
    return True

def check_proxy(proxy: Proxy) -> bool:
    try:
        response = requests.get(
            TEST_URLS[0],
            proxies={proxy.protocol: proxy.link},
            timeout=CHECK_TIMEOUT_SECONDS,
        )
        return response.status_code == 200
    except:
        return False


def check_worker(proxy_queue: queue.Queue, callback_queue: queue.Queue):
    while True:
        data: typing.Union[str, Proxy] = proxy_queue.get()
        if data == "EXIT":
            return
        if check_proxy(data):
            callback_queue.put(data)


def load_proxies(types=["http", "socks4", "socks5"]):
    proxies = []
    for i in types:
        with open(i + ".txt", "r") as f:
            data = f.read().strip().split("\n")
            for j in data:
                proxies.append(Proxy(i, j))
    return proxies


def main(workers: int, types=["http", "socks4", "socks5"]):
    rich.print(f"[green]I[/green]: Worker number: {workers}")
    rich.print(f"[green]I[/green]: Check timeout: {CHECK_TIMEOUT_SECONDS}s")
    if not check_socks():
        rich.print(
            f"[yellow]W[/yellow]: Missing dependencies for SOCKS support. Please run `pip install pysocks`."
        )
        if os.getenv("CONTINUE_WITHOUT_SOCKS", "N") != "y":
            exit(1)
    rich.print("[green]I[/green]: Loading proxies")
    proxies = load_proxies(types=types)
    random.shuffle(proxies)
    proxy_queue = queue.Queue()
    callback_queue = queue.Queue()
    for proxy in proxies:
        proxy_queue.put(proxy)
    rich.print("[green]I[/green]: Starting workers")
    for _ in range(workers):
        threading.Thread(
            target=check_worker, args=(proxy_queue, callback_queue)
        ).start()
    rich.print("[green]I[/green]: Check started!")
    last_checked = 0
    with rich.progress.Progress(
        rich.progress.TextColumn("[green]I[/green]: "),
        rich.progress.SpinnerColumn(),
        rich.progress.TextColumn("[progress.description]{task.description}"),
        rich.progress.BarColumn(),
        rich.progress.TaskProgressColumn(),
        rich.progress.TextColumn("  "),
        rich.progress.TimeElapsedColumn(),
        rich.progress.TextColumn(":"),
        rich.progress.TimeRemainingColumn(),
        rich.progress.MofNCompleteColumn()
    ) as progress:
        task = progress.add_task("Checking...", total=len(proxies))
        while not proxy_queue.empty():
            pending = proxy_queue.qsize()
            checked = len(proxies) - pending
            checked_this_loop = checked - last_checked
            last_checked = checked
            progress.update(task, advance=checked_this_loop)
            time.sleep(0.1)  # 减少间隔时间
    checked_proxies = []
    while not callback_queue.empty():
        checked_proxies.append(callback_queue.get())
    rich.print(f"[green]I[/green]: Writing {len(checked_proxies)} proxies to checked_proxies.txt")
    results = {}
    for proxy in checked_proxies:
        proxy: Proxy
        if proxy.protocol in results.keys():
            results[proxy.protocol].append(proxy.address)
        else:
            results[proxy.protocol] = [proxy.address]
    for i in types:
        with open(f"{i}_checked.txt", "w+") as f:
            f.write("\n".join(results.get(i, [])))
    rich.print(f"[green]I[/green]: Done!")
    for _ in range(workers):
        proxy_queue.put("EXIT")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        workers = sys.argv[1]
    else:
        workers = input("Worker number: (32)")
    if not workers or not workers.isdigit():
        workers = 32
    else:
        workers = int(workers)
    if workers >= 4096:
        rich.print(f"[yellow]W[/yellow]: It is not recommended to use more than 4096 workers.")
    main(workers)
