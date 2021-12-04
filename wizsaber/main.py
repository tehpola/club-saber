from .club import Club
import asyncio


async def main():
    club = Club()
    await club.init()
    await club.run()


if __name__ == '__main__':
    asyncio.run(main())

