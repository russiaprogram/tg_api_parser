# Telegram Chat Parser

`tg_api_parser` is a utility for downloading messages and media files from a Telegram chat or channel using Pyrogram library through API. It saves messages and service events (like users joining/leaving) into convenient CSV files and has an option of downloading all media files into a separate folder.

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/tg_api_parser.git
cd tg_api_parser
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and add your Telegram API keys (get them from my.telegram.org):

```
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
```

## Usage

### Command Line Interface

Run the script from the command line:

```bash
python -m tg_api_data_parser -c CHAT_ID [OPTIONS]
```

**Required arguments**
- `-c`, `--chat_id` — Chat or channel ID (e.g., `-1001234567890` for supergroups, or `@channelname`).

**Optional arguments**
- `-l`, `--limit` — Maximum number of messages to fetch. *(default: all available)*
- `-f`, `--folder` — Folder path to save files and CSVs. *(default: current directory)*
- `-s`, `--save_actions` — Save service messages (join/leave the chat).
- `-m`, `--save_files` — Download media files (photos, documents, videos, etc.).

### Python Library

You can also use the parser as a Python library in your applications:

```python
import asyncio
from tg_api_parser import TgApiParser

async def main():
    # Initialize parser
    parser = TgApiParser(
        chat_id=-1001234567890, #should be replaces with the chat id you want to parse
        api_id="your_api_id",  # optional if set in .env
        api_hash="your_api_hash",  # optional if set in .env
        output_path="./downloads"
    )
    
    # Load messages
    await parser.load_data(limit=1000)
    
    # Extract structured data
    parser.extract_messages()
    
    # Download media files (optional)
    await parser.get_files()
    
    # Save to CSV
    parser.save_chat(save_actions=True)

# Run the async function
asyncio.run(main())
```

### Jupyter Notebooks

```python
# In a Jupyter cell
import asyncio
from tg_api_parser import TgApiParser

parser = TgApiParser(chat_id="@channel_name")
await parser.load_data(limit=500)
parser.extract_messages()

# Analyze with pandas
import pandas as pd
df = pd.DataFrame(parser.content_messages)
print(df['media_type'].value_counts())
```

## Output

After running, the following will appear in the specified folder:
- `content_messages.csv` — all messages
- `member_actions.csv` *(if `-s` is set for CLI and `parser.save_chat(save_actions=True)` for the library)* — service messages
- `files/` *(if `-m` is set for CLI and `await parser.get_files()` is launched for the librabry)* — downloaded media files

## Requirements

- Python 3.8+
- Pyrogram
- python-dotenv
- tqdm

## License

MIT License. Free to use and modify for your own needs.