import argparse
import asyncio
from async_server import AsyncServer
from caching import Cache, CsvCacheManager

parser = argparse.ArgumentParser()
parser.add_argument(
    '--load', help='name of file to load cache from')
parser.add_argument(
    '--save', required=True,
    help='name of file to save cache in')


def main():
    loop = asyncio.get_event_loop()

    args = parser.parse_args()
    if args.load:
        cache = CsvCacheManager.load_cache_from(args.load)
    else:
        cache = Cache()

    server = AsyncServer(loop, cache)
    try:
        loop.create_task(server.run())
        loop.run_forever()
        #loop.run_until_complete(server.run())
    except KeyboardInterrupt:
        print('Server shutdown')
    finally:
        CsvCacheManager.save_cache_to(server.cache, args.save)
    
       
if __name__ == "__main__":
    main()