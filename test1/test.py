import time
import docker
import requests
import os
import shutil
import subprocess
import requests_unixsocket
import statistics
import concurrent
import json


def time_func(func):
    def wrapper(*args, **kwargs):

        t = time.time()

        r = func(*args, **kwargs)

        t = time.time() - t

        return r, t
    return wrapper


12


class serverless_test_container:

    def __init__(self, service_file='test_container/user_service.py', port=5000, init=False, swap=False, pause=False):
        self._swap = swap
        self._service_file = service_file
        self._port = port
        self._inited = init
        self._paused = pause

        if init:
            self.init()

        if swap:
            self.swap()

        if pause:
            self.pause()

    def init(self):
        '''
        Initialize a container for one test instance.
        '''
        raise NotImplementedError

    def swap(self):
        '''
        Put an initialized container to swap.
        '''
        raise NotImplementedError

    def unswap(self):
        '''
        Allow a swapped container to move back to RAM.
        '''
        raise NotImplementedError

    def pause(self):
        '''
        Pause the test container.
        '''
        raise NotImplementedError

    def unpause(self):
        '''
        Unpause the test container.
        '''
        raise NotImplementedError

    def run(self, test_req):
        '''
        Run the test content.
        '''
        if not self._inited:
            raise RuntimeError
        res = requests.post(
            'http://127.0.0.1:{}/call'.format(self._port), json=test_req)
        return res.json()

    def get_time(self):
        '''
        Get test times.
        '''
        if not self._inited:
            raise RuntimeError
        res = requests.get(
            'http://127.0.0.1:{}/times'.format(self._port))
        return res.json()

    def cleanup(self):
        '''
        Celanup the container.
        '''
        raise NotImplementedError


class firecracker_test_container(serverless_test_container):
    count = 0

    def __init__(self, service_file='test_container/user_service.py', port=5000, init=False, swap=False, pause=False):

        super().__init__(service_file, port, init, swap, pause)

        self.id = firecracker_test_container.count
        self.idstr = 'test_serverless_firecracker_{}'.format(self.id)
        firecracker_test_container.count += 1

        self._mkrootfs = False
        self.rootfs = './test_root.{}.img'.format(
            self.id)
        self.socket = './firecracker.{}.socket'.format(
            self.id)
        self.kernel = './vmlinux.bin'

    def __del__(self):
        pass

    def make_rootfs(self):

        shutil.copyfile(self._service_file, './test_root/app/user_service.py')
        subprocess.run(
            [
                'dd',
                'if=/dev/zero',
                'of={}'.format(self.rootfs),
                'bs=1M',
                'count=120'
            ]
        )
        subprocess.run(['mkfs.ext4', self.rootfs])
        subprocess.run(['sh', '-c', 'sudo rm -rf /tmp/mount'])
        os.mkdir('/tmp/mount')
        subprocess.run(['sudo', 'mount', self.rootfs, '/tmp/mount'])
        subprocess.run(['sh', '-c', 'sudo cp -R test_root/* /tmp/mount'])
        subprocess.run(['sudo', 'umount', self.rootfs])
        self._mkrootfs = True

    def init(self):
        '''
        Initialize a container for one test instance.
        '''
        if not self._mkrootfs:
            raise RuntimeError
        subprocess.run(
            [
                '/usr/local/bin/jailer',
                '--id', self.idstr,
                '--uid', '1000',
                '--gid', '1000',
                '--node', '0',
                '--daemonize',
                '--exec-file', '/usr/local/bin/firecracker'
            ]
        )

    def swap(self):
        '''
        Put an initialized container to swap.
        '''
        raise NotImplementedError

    def unswap(self):
        '''
        Allow a swapped container to move back to RAM.
        '''
        raise NotImplementedError

    def pause(self):
        '''
        Pause the test container.
        '''
        raise NotImplementedError

    def unpause(self):
        '''
        Unpause the test container.
        '''
        raise NotImplementedError

    def cleanup(self):
        '''
        Celanup the container.
        '''
        raise NotImplementedError


def find_min_memory_limit(set_memory_limit: callable, exp, start=0x200000000, swap_breath=0.010):
    limit = int(start)
    decrement = int(limit / 2)

    while True:
        while True:
            try:
                limit -= decrement
                set_memory_limit(limit)
                time.sleep(swap_breath)
                break
            except exp:
                limit += decrement
                if decrement >= 2:
                    decrement = int(decrement / 2)
                else:
                    return

        if limit < 2:
            return

        decrement = int(limit / 2)


class docker_test_container(serverless_test_container):

    d = docker.from_env()

    def __init__(self, docker_img='benbenng/serverless_test:http', service_file='test_container/user_service.py', port=5000, init=False, swap=False, pause=False):
        super().__init__(service_file, port, init, swap, pause)
        self.docker_img = docker_img

    def init(self):
        '''
        Initialize a container for one test instance.
        '''
        self.container = docker_test_container.d.containers.run(
            self.docker_img,
            remove=False,
            detach=True,
            mem_limit='4g',
            memswap_limit='4g',
            volumes={
                os.path.abspath(self._service_file):
                    {
                        'bind': '/app/user_service.py',
                        'mode': 'rw'
                }
            },
            ports={
                '5000/tcp': ('0.0.0.0', self._port)
            }
        )
        self._inited = True

    def swap(self):
        '''
        Put an initialized container to swap.
        '''
        if not self._inited:
            raise RuntimeError

        def set_memory_limit(limit):
            self.container.update(mem_limit=str(int(limit)))

        find_min_memory_limit(
            set_memory_limit, docker.errors.APIError, start=0x100000000)
        self._swap = True

    def unswap(self):
        '''
        Allow a swapped container to move back to RAM.
        '''
        if not self._inited:
            raise RuntimeError
        self.container.update(mem_limit='4g')
        self._swap = False

    def pause(self):
        '''
        Pause the test container.
        '''
        if not self._inited:
            raise RuntimeError
        self.container.pause()
        self._paused = True

    def unpause(self):
        '''
        Unpause the test container.
        '''
        if not self._inited:
            raise RuntimeError
        self.container.unpause()
        self._paused = False

    def cleanup(self):
        '''
        Celanup the container.
        '''
        if not self._inited:
            raise RuntimeError
        self.container.stop()
        self.logs = self.container.logs()
        self.container.remove()

    def mem_usage(self):
        try:
            stats = self.container.stats(decode=True, stream=True)
            f = stats.__next__()['memory_stats']
            return f['usage']
        except BaseException as e:
            print(f)
            raise e


def test_cold_start(test='http', repeat=5, init_wait=0.5, cache_wait=0.5):
    startup_times = []
    cleanup_times = []
    run_times = []
    ready_mem_usages = []
    run_mem_usages = []

    for _ in range(repeat):
        s = time.time()
        d = docker_test_container(
            'benbenng/serverless_test:{}'.format(test), 'service_{}.py'.format(test))
        d.init()
        retry = 3
        while retry > 0:
            retry -= 1
            try:
                d.run({})
            except requests.exceptions.ConnectionError:
                retry += 1
        times = d.get_time()
        ready_mem_usages.append(d.mem_usage())
        run_mem_usages.append(d.mem_usage())
        a = time.time()
        d.cleanup()
        t = time.time() - a
        startup_times.append(times['call'][0][0]-s)
        cleanup_times.append(t)
        run_times.append(sum([t-s for s, t in times['call']]))
    return startup_times, cleanup_times, run_times, ready_mem_usages, run_mem_usages


def test_warm_start(test='http', repeat=5, init_wait=0.5, cache_wait=0.5):
    startup_times = []
    cleanup_times = []
    run_times = []
    ready_mem_usages = []
    run_mem_usages = []

    for _ in range(repeat):
        d = docker_test_container(
            'benbenng/serverless_test:{}'.format(test), 'service_{}.py'.format(test))
        d.init()
        time.sleep(init_wait)
        s = time.time()
        retry = 3
        while retry > 0:
            retry -= 1
            try:
                d.run({})
            except requests.exceptions.ConnectionError:
                retry += 1
        times = d.get_time()
        ready_mem_usages.append(d.mem_usage())
        run_mem_usages.append(d.mem_usage())
        a = time.time()
        d.cleanup()
        t = time.time() - a
        startup_times.append(times['call'][0][0]-s)
        cleanup_times.append(t)
        run_times.append(sum([t-s for s, t in times['call']]))
    return startup_times, cleanup_times, run_times, ready_mem_usages, run_mem_usages


def test_swapped_start(test='http', repeat=5, init_wait=0.5, cache_wait=0.5):
    startup_times = []
    cleanup_times = []
    run_times = []
    ready_mem_usages = []
    run_mem_usages = []

    for _ in range(repeat):
        d = docker_test_container(
            'benbenng/serverless_test:{}'.format(test), 'service_{}.py'.format(test))
        d.init()
        time.sleep(init_wait)
        d.swap()
        time.sleep(cache_wait)
        ready_mem_usages.append(d.mem_usage())
        s = time.time()
        d.unswap()
        retry = 3
        while retry > 0:
            retry -= 1
            try:
                d.run({})
            except requests.exceptions.ConnectionError:
                retry += 1
        times = d.get_time()
        run_mem_usages.append(d.mem_usage())
        a = time.time()
        d.cleanup()
        t = time.time() - a
        startup_times.append(times['call'][0][0]-s)
        cleanup_times.append(t)
        run_times.append(sum([t-s for s, t in times['call']]))
    return startup_times, cleanup_times, run_times, ready_mem_usages, run_mem_usages


def test_paused_start(test='http', repeat=5, init_wait=0.5, cache_wait=0.5):
    startup_times = []
    cleanup_times = []
    run_times = []
    ready_mem_usages = []
    run_mem_usages = []

    for _ in range(repeat):
        d = docker_test_container(
            'benbenng/serverless_test:{}'.format(test), 'service_{}.py'.format(test))
        d.init()
        time.sleep(init_wait)
        d.pause()
        time.sleep(cache_wait)
        ready_mem_usages.append(d.mem_usage())
        s = time.time()
        d.unpause()
        retry = 3
        while retry > 0:
            retry -= 1
            try:
                d.run({})
            except requests.exceptions.ConnectionError:
                retry += 1
        times = d.get_time()
        run_mem_usages.append(d.mem_usage())
        a = time.time()
        d.cleanup()
        t = time.time() - a
        startup_times.append(times['call'][0][0]-s)
        cleanup_times.append(t)
        run_times.append(sum([t-s for s, t in times['call']]))
    return startup_times, cleanup_times, run_times, ready_mem_usages, run_mem_usages


def test_docker(test='http', repeat=5, init_wait=0.5, cache_wait=0.5):
    print()
    print()
    print('Test Docker {}'.format(test))

    test_results = {}

    for txt, fx in [
        ('Cold Start', test_cold_start),
        ('Warm Start', test_warm_start),
        ('Swapped Start', test_swapped_start),
        ('Paused Start', test_paused_start)
    ]:

        startup_times, cleanup_times, run_times, ready_mem_usages, run_mem_usages = fx(
            test, repeat, init_wait, cache_wait)
        print(txt)
        test_results[txt] = {
            'startup': startup_times,
            'cleanup': cleanup_times,
            'run': run_times,
            'mem_ready': ready_mem_usages,
            'mem_run': run_mem_usages
        }

    return test_results


if __name__ == '__main__':
    # for t, iw, cw in [('http', 1, 1)]:
    for t, iw, cw in [('mxnet', 30, 10)]:
        json.dump(test_docker(t, repeat=10, init_wait=iw,
                              cache_wait=cw), open('test_{}.log'.format(t), 'w'), indent=4)
