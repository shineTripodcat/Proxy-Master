import threading
import queue
import requests
import typing
import time
import sys
import random

try:
    import rich
    import rich.progress
    import rich.progress_bar
except ImportError:
    print("此代理检查器需要 rich 库才能工作。\n请尝试 pip3 install rich 。")
    exit(1)

CHECK_TIMEOUT_SECONDS = 5

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


def check_proxy(proxy: Proxy) -> bool:
    test_urls = [
        "https://httpbin.org/ip",
        "https://api.ipify.org",
        "https://api.ipify.org?format=json",
        "https://ipinfo.io"
    ]
    for url in test_urls:
        try:
            response = requests.get(
                url,
                proxies={
                    "https": proxy.link,
                    "http": proxy.link,
                    "socks4": proxy.link,
                    "socks5": proxy.link,
                },
                timeout=CHECK_TIMEOUT_SECONDS
            )
            if response.status_code == 200:
                return True
        except:
            continue
    return False


def check_worker(proxy_queue: queue.Queue, callback_queue: queue.Queue):
    while 1:
        data: typing.Union[str, Proxy] = proxy_queue.get()
        if data == "EXIT":
            return
        if check_proxy(data):
            callback_queue.put(data)


def load_proxies(types=["http", "socks4", "socks5"]):
    proxies = []
    for i in types:
        with open(i + ".txt", "r") as f:
            data = f.read().strip("\n")
            data = data.split("\n")
            for j in data:
                proxies.append(Proxy(i, j))
    return proxies


def main(workers: int, types=["http", "socks4", "socks5"]):
    rich.print(f"[green]I[/green]: 工作线程数量: {workers}")
    rich.print(f"[green]I[/green]: 检查超时时间: {CHECK_TIMEOUT_SECONDS}s")
    if not check_socks():
        rich.print(
            f"[yellow]W[/yellow]: 缺少 SOCKS 支持的依赖项。请运行 `pip install pysocks`。"
        )
        if input("继续而不检查 SOCKS 代理？(y/N): ") != "y":
            exit(1)
    rich.print("[green]I[/green]: 正在加载代理")
    proxies = load_proxies(types=types)
    random.shuffle(proxies)
    proxy_queue = queue.Queue()
    callback_queue = queue.Queue()
    for proxy in proxies:
        proxy_queue.put(proxy)
    rich.print("[green]I[/green]: 启动工作线程")
    for _ in range(workers):
        threading.Thread(
            target=check_worker, args=(proxy_queue, callback_queue)
        ).start()
    rich.print("[green]I[/green]: 开始检查！")
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
            time.sleep(0.5)
    checked_proxies = []
    while not callback_queue.empty():
        checked_proxies.append(callback_queue.get())
    rich.print(f"[green]I[/green]: 将 {len(checked_proxies)} 个代理写入 x_checked.txt")
    results = {}
    for proxy in checked_proxies:
        proxy
        if proxy.protocol in results.keys():
            results[proxy.protocol].append(proxy.address)
        else:
            results[proxy.protocol] = [proxy.address]
    for i in types:
        with open(f"{i}_checked.txt", "w+") as f:
            f.write("\n".join(results.get(i, [])))
    rich.print(f"[green]I[/green]: 完成！")
    for _ in range(workers):
        proxy_queue.put("EXIT")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        workers = sys.argv[1]
    else:
        workers = input("工作线程数量: (32)")
    if not workers or not workers.isdigit():
        workers = 32
    else:
        workers = int(workers)
    if workers >= 4096:
        rich.print(f"[yellow]W[/yellow]: 不建议使用超过 4096 个工作线程。")
    main(workers)
