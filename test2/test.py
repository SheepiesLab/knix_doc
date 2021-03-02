import os
import signal
import time
import subprocess
import json


def cgcreate():
    subprocess.run(['cgcreate', '-g', 'memory:test'])


def cgclassify(pid):
    subprocess.run(['cgclassify', '-g', 'memory:test', str(int(pid))])


def cgdelete():
    subprocess.run(['cgdelete', '-g', 'memory:test'])


def set_swappiness(s):
    with open("/sys/fs/cgroup/memory/{}/memory.swappiness".format('test'), 'w') as f:
        f.write(str(int(s)))


def get_swappiness():
    with open("/sys/fs/cgroup/memory/{}/memory.swappiness".format('test'), 'r') as f:
        return int(f.read())


def set_memory_limit(limit):
    with open("/sys/fs/cgroup/memory/{}/memory.limit_in_bytes".format('test'), 'w') as f:
        f.write(str(int(limit)))


def get_memory_limit():
    with open("/sys/fs/cgroup/memory/{}/memory.limit_in_bytes".format('test'), 'r') as f:
        return int(f.read())


def find_min_memory_limit(start=0x200000000, swap_breath=0.010):
    limit = int(start)
    decrement = int(limit / 2)

    while True:
        while True:
            try:
                limit -= decrement
                set_memory_limit(limit)
                time.sleep(swap_breath)
                break
            except:
                limit += decrement
                if decrement >= 2:
                    decrement = int(decrement / 2)
                else:
                    return get_memory_limit()

        if limit < 2:
            return get_memory_limit()

        decrement = int(limit / 2)


class test_memory_allocator:

    def __init__(self, memsize):
        self.memsize = memsize
        self.pid = os.fork()
        if self.pid == 0:
            # Child
            os.execl("./a.out", "./a.out", str(int(self.memsize)))
            # END
        else:
            # Parent
            print("Memory Allocator PID: {}".format(self.pid))

    def sig(self):
        os.kill(self.pid, signal.SIGINT)

    def wait(self):
        os.kill(self.pid, signal.SIGINT)
        os.waitpid(self.pid, 0)


def test(start, end, step, repeat=1, scale="exp"):
    if step > 1:
        def f(s, t): return s < t
    else:
        def f(s, t): return s > t

    if scale == "exp":
        def sp(start, step): return start * step
    elif scale == "lin":
        def sp(start, step): return start + step
    else:
        def sp(start, step): return start * step

    cgcreate()
    while f(start, end):
        limit = []
        t = []
        for _ in range(repeat):
            test_process = test_memory_allocator(start)

            set_swappiness(60)
            set_memory_limit(start * 2)
            cgclassify(test_process.pid)
            test_process.sig()

            set_swappiness(100)
            limit.append(find_min_memory_limit(start=start, swap_breath=0.010))

            time.sleep(0.050)
            s = time.time()
            set_swappiness(60)
            set_memory_limit(start * 2)
            test_process.sig()
            test_process.wait()
            t.append(time.time() - s)

        yield {
            "process_size": start,
            "min_resident_memory": limit,
            "retrival_time": t
        }

        start = sp(start, step)
    cgdelete()


def readable_bytefmt(size):
    G = int(size / (1024 * 1024 * 1024))
    M = int((size - G * 1024 * 1024 * 1024)/(1024*1024))
    K = int((size - G * 1024 * 1024 * 1024 - M * 1024 * 1024)/(1024))
    B = size - G * 1024 * 1024 * 1024 - M * 1024 * 1024 - K * 1024
    return "{}G {}M {}K {}B".format(G, M, K, B)


if __name__ == "__main__":
    with open("log", 'a') as f:
        l = list(test(0x20000, 0x100000000, 2, 10))
        json.dump(l, f, indent=4)

    os.chown("log", 1000, 1000)
