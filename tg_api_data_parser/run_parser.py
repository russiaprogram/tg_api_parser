import asyncio
import argparse

from .parser import TgApiParser
from dotenv import load_dotenv

load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Telegram chat parser: download messages, media, and export to CSV."
    )
    parser.add_argument(
        "-c", "--chat_id", required=True, help="Target chat/channel ID (e.g., -1001234567890)"
    )
    parser.add_argument(
        "-l", "--limit", type=int, default=None, help="Max number of messages to fetch"
    )
    parser.add_argument(
        "-f", "--folder", type=str, default=None, help="Folder to save downloaded media and CSVs"
    )
    parser.add_argument(
        "-s", "--save_actions", action="store_true",
        help="Save service messages (like join/leave) to CSV"
    )
    parser.add_argument(
        "-m", "--save_files", action="store_true",
        help="Download media files"
    )
    return parser.parse_args()


async def main_async(args):
    parser = TgApiParser(chat_id=args.chat_id, output_path=args.folder)
    print(f"Loading messages from chat {args.chat_id} ...")
    await parser.load_data(limit=args.limit)

    print("Extracting message content ...")
    parser.extract_messages()

    if args.save_files:
        print("Downloading media files ...")
        await parser.get_files()

    print("Saving chat to CSV ...")
    parser.save_chat(save_actions=args.save_actions)

    print("Done!")


def main():
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

