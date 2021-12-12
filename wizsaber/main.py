from wizsaber.club import Club
import asyncio


async def async_main():
    club = Club()
    await club.init()
    await club.run()


def main():
    asyncio.run(async_main())


if __name__ == '__main__':
    main()

