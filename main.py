import argparse
from server import Server
from caching import Cache, CsvCacheManager

parser = argparse.ArgumentParser()
parser.add_argument(
    '--load', help='name of file to load cache from')
parser.add_argument(
    '--save', required=True,
    help='name of file to save cache in')


def main():
    args = parser.parse_args()
    if args.load:
        cache = CsvCacheManager.load_cache_from(args.load)
    else:
        cache = Cache()

    server = Server(cache)
    try:
        server.run()
    except KeyboardInterrupt:
        print('Server shutdown')
    finally:
        CsvCacheManager.save_cache_to(server.cache, args.save)
    
       
if __name__ == "__main__":
    main()