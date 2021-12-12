from .club import Club
import asyncio


async def async_main():
    club = Club()
    await club.init()
    await club.run()


def main():
    asyncio.run(main())


if __name__ == '__main__':
    main()

