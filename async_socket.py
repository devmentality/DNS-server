# UDP sockets wrapper from https://www.pythonsheets.com/notes/python-asyncio.html

class AsyncSocket:
    def __init__(self, loop, sock):
        self.loop = loop
        self.sock = sock
    
    def recvfrom(self, n_bytes, fut=None, registed=False):
        fd = self.sock.fileno()
        if fut is None:
            fut = self.loop.create_future()
        if registed:
            self.loop.remove_reader(fd)

        try:
            data, addr = self.sock.recvfrom(n_bytes)
        except (BlockingIOError, InterruptedError):
            self.loop.add_reader(fd, self.recvfrom, n_bytes, fut, True)
        else:
            fut.set_result((data, addr))
        return fut

    def sendto(self, data, addr, fut=None, registed=False):
        fd = self.sock.fileno()
        if fut is None:
            fut = self.loop.create_future()
        if registed:
            self.loop.remove_writer(fd)
        if not data:
            return

        try:
            n = self.sock.sendto(data, addr)
        except (BlockingIOError, InterruptedError):
            self.loop.add_writer(fd, self.sendto, data, addr, fut, True)
        else:
            fut.set_result(n)
        return fut
