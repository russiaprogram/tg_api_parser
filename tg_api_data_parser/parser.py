import os
import asyncio
import csv

from pyrogram import Client
from dotenv import load_dotenv
from tqdm import tqdm

from pyrogram.errors import FloodWait, RPCError

# Load environment variables
load_dotenv()

class TgApiParser():
    """
    Telegram API Parser.

    A wrapper around the Pyrogram client for downloading messages and media 
    from Telegram chats, groups, or channels. The class provides methods to 
    load message history, save media files, and export structured data.

    Parameters
    ----------
    chat_id : int or str
        Unique identifier for the target chat (can be channel, group, or user).
    api_id : int, optional
        Telegram API ID. If not provided, it will be read from the environment 
        variable ``TG_API_ID``.
    api_hash : str, optional
        Telegram API hash. If not provided, it will be read from the environment 
        variable ``TG_API_HASH``.
    output_path : str, optional
        Directory path for saving files and results. If not specified, defaults 
        to ``Chat_<chat_id>`` inside the current working directory.

    Attributes
    ----------
    api_id : int
        API ID used to authenticate with Telegram.
    api_hash : str
        API hash used to authenticate with Telegram.
    chat_id : int or str
        Target chat identifier.
    output_path : str
        Path to the output directory where files are saved.
    messages : list of pyrogram.types.Message
        List of loaded messages from the chat.
    
    Raises
    ------
    ValueError
        If neither `api_id` nor `api_hash` are provided (via arguments or environment).
    
    Notes
    -----
    - Requires environment variables ``TG_API_ID`` and ``TG_API_HASH`` 
      if `api_id` and `api_hash` are not explicitly passed.
    - Automatically creates the output directory if it does not exist.
    """

 
    
    def __init__(self, chat_id, api_id=None, api_hash=None, output_path=None):
        """
        Initialize the Telegram API parser.

        Notes
        -----
        This constructor initializes the Pyrogram client session and ensures that
        the output directory exists.
        """
    
        self.api_id = int(api_id) if api_id else int(os.getenv('TG_API_ID'))
        self.api_hash = api_hash or os.getenv('TG_API_HASH')
        self.chat_id = chat_id

        self.output_path = output_path or os.path.join(os.getcwd(), f"Chat_{chat_id}")
        self.path_created = False

        if not self.api_id or not self.api_hash:
            raise ValueError("TG_API_ID or TG_API_HASH is missing")
        
        self.messages = []

    async def load_data(self, limit=None, retries=3):
        """
        Load message history from the target chat.

        Parameters
        ----------
        limit : int, optional
            Maximum number of messages to load. If None, loads all available messages.
        retries : int, optional
            Number of times to retry the request in case of a FloodWait error.
            Defaults to 3.

        Returns
        -------
        list of pyrogram.types.Message
            A list of Telegram message objects loaded from the chat.

        Raises
        ------
        RuntimeError
            If the client session could not be started, the chat history is
            inaccessible, or retries are exhausted.
        """

        client = Client("my_session", api_id=self.api_id, api_hash=self.api_hash)

        attempt = 0
        while attempt < retries:
            try:
                async with client:
                    self.messages = [
                        msg async for msg in client.get_chat_history(self.chat_id, limit=limit)
                    ]
                return self.messages.reverse()  # Return messages in chronological order

            except FloodWait as e:
                attempt += 1
                wait_time = e.value + 2  # wait time specified by Telegram + 2s buffer
                if attempt < retries:
                    print(
                        f"FloodWait: sleeping {wait_time}s "
                        f"before retry {attempt}/{retries}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"FloodWait exceeded after {retries} retries "
                        f"(last wait was {wait_time}s)."
                    ) from e

            except RPCError as e:
                raise RuntimeError(f"Telegram API error: {e}") from e

            except Exception as e:
                raise RuntimeError(f"Failed to load chat history: {e}") from e

    def extract_messages(self):
        """
        Parse messages loaded from the Telegram API into structured dictionaries.

        This method separates **content messages** (regular user messages) and 
        optionally **service messages** (member joins, leaves, etc.), storing them 
        in `self.content_messages` and `self.member_actions` respectively.

        Notes
        -----
        - Requires `load_data()` to have been called first.
        - `self.content_messages` is a list of dictionaries with keys like
        'msg_id', 'posting_time', 'sender', 'media_type', 'file_id', etc.
        - `self.member_actions` is a list of lists of dictionaries, each representing
        a member join/leave event.

        Raises
        ------
        AttributeError
            If `self.messages` is empty (i.e., `load_data()` was not called).
        """

        if not hasattr(self, "messages") or not self.messages:
            raise AttributeError("No messages loaded. Call load_data() first.")

        # Parse content messages.
        self.content_messages = [
            self._parse_content_message(msg) 
            for msg in self.messages 
            if not msg.service
        ]

        # Parse service messages.
        self.member_actions = [
            self._parse_service_message(msg) for msg in self.messages 
            if msg.service
            ]


    async def get_files(self, retries=3):
        """
        Download media files from all parsed messages.

        Stores downloaded file paths in the corresponding content_messages 
        dictionaries under the key 'file', as paths relative to the current working 
        directory. All content_messages will have the 'file' key initialized to None
        before download, ensuring consistent CSV columns.

        Parameters
        ----------
        retries : int, optional
            Number of retries in case of FloodWait. Default is 3.
        """
        
        # Create output directory if it doesn't exist.
        if self.path_created is False:
            os.makedirs(self.output_path, exist_ok=True)
            self.path_created = True

        cwd = os.getcwd()  # base for relative paths

        # Initialize 'file' key for all messages
        for cm in self.content_messages:
            cm['file'] = None

        async with Client("my_session", api_id=self.api_id, api_hash=self.api_hash) as client:
            for msg in tqdm(self.messages):
                if not msg.media:
                    continue

                attempt = 0
                while attempt < retries:
                    try:
                        # Download media
                        abs_file_path = await client.download_media(
                            msg, 
                            file_name=os.path.join(self.output_path, 'files/')
                        )

                        # Convert to relative path
                        rel_file_path = os.path.relpath(abs_file_path, start=cwd)

                        # Update the corresponding content_message
                        for cm in self.content_messages:
                            if cm['msg_id'] == msg.id:
                                cm['file'] = rel_file_path
                                break

                        break  # success, exit retry loop

                    except FloodWait as e:
                        attempt += 1
                        wait_time = e.value + 2
                        if attempt < retries:
                            print(f"FloodWait: sleeping {wait_time}s before retry {attempt}/{retries}")
                            await asyncio.sleep(wait_time)
                        else:
                            print(f"FloodWait exceeded for message {msg.id}, skipping.")
                            break

                    except RPCError as e:
                        print(f"Telegram API error for message {msg.id}: {e}")
                        break

                    except Exception as e:
                        print(f"Failed to download media {msg.media} for message {msg.id}: {e}")
                        break


    def save_chat(self, save_actions=False):
        """
        Export content messages and optionally member actions to CSV files
        in the specified output directory.

        Parameters
        ----------
        save_actions : bool, optional
            If True, also parse and store service messages in `self.member_actions`.
            Default is False.

        """    
        # Create output directory if it doesn't exist.
        if self.path_created is False:
            os.makedirs(self.output_path, exist_ok=True)
            self.path_created = True

        if not hasattr(self, 'content_messages') or not self.content_messages:
            raise AttributeError("No content messages found. Call extract_messages() first.")

        # Save member actions if applicable.
        if save_actions:
            if len(self.member_actions) > 0:
                self._save_to_csv(os.path.join(self.output_path, 'member_actions.csv'), self.member_actions)
            else:
                print('No service messages.')

        self._save_to_csv(os.path.join(self.output_path, 'content_messages.csv'), self.content_messages)


    def _save_to_csv(self, csv_path, messages, encoding='utf-8'):
        """
        Saves a list of message dictionaries to a CSV file with consistent columns.

        Parameters
        ----------
        csv_path : str
            Full path to save the CSV file.
        messages : list of dict
            Messages to save.
        encoding : str
            File encoding (default 'utf-8').
        """
        if not messages:
            raise IndexError("No messages to save.")
        
        fieldnames = messages[0].keys()

        # Write CSV
        with open(csv_path, 'w', newline='', encoding=encoding) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(messages)


    def _parse_content_message(self, message):
        """
        Parse a Telegram message into a structured dictionary.

        This method transforms a single Pyrogram message object into a consistent
        dictionary with predefined keys for metadata, sender/forward information,
        media content, and chat details. Even service messages (like member joins/leaves)
        will return a dictionary with all keys, initialized to None, ensuring
        uniform structure for CSV export or further processing.

        Parameters
        ----------
        message : pyrogram.types.Message
            A single message object fetched via Pyrogram.

        Returns
        -------
        dict
            Dictionary containing the following keys:

            - msg_id : int or None
                Unique identifier of the message.
            - posting_time : datetime.datetime or None
                Time when the message was sent.
            - edited : datetime.datetime or None
                Time when the message was last edited.
            - reply_to_msg_id : int or None
                ID of the message this message replies to, if any.
            - views : int or None
                Number of views for the message.
            - reactions : object or None
                Reactions associated with the message.
            - reactions_count : object or None
                Count reactions associated with the message.
            - sender : str or None
                Type of sender ('user' or 'group').
            - sender_id : int or None
                Telegram ID of the sender.
            - sender_name : str or None
                Username or title of the sender.
            - forward_from : str or None
                Type of original sender for forwarded messages ('user' or 'chat').
            - forward_id : int or None
                ID of the original sender, if available.
            - forward_name : str or None
                Username or title of the original sender, if available.
            - media_type : str or None
                Type of attached media (photo, video, document, etc.) or 'text'.
            - file_id : str or None
                Telegram file ID for the media, if any.
            - content : str or None
                Text content of the message or media caption/description.
            - file_name : str or None
                Original filename for documents or other media, if available.
            - chat_id : int or None
                ID of the chat where the message was sent.
            - chat_name : str or None
                Title of the chat.
            """


        # Initialize the keys with None
        message_dict = {
            'msg_id': None,
            'posting_time': None,
            'edited': None,
            'reply_to_msg_id': None,
            'views': None,
            'reactions': None
        }

        if message and not message.service:
            # Populate message metadata
            message_dict['msg_id'] = message.id
            message_dict['posting_time'] = message.date
            message_dict['edited'] = message.edit_date
            message_dict['reply_to_msg_id'] = message.reply_to_message_id
            message_dict['views'] = message.views
            message_dict['reactions'] = self._get_reactions(message)[0]
            message_dict['reactions_count'] = self._get_reactions(message)[1]

            # Get sender information
            sender_dict = self._get_sender(message)
            message_dict.update(sender_dict)

            # Get forward information
            forward_dict = self._get_forward(message)
            message_dict.update(forward_dict)

            # Get media information
            media_dict = self._parse_media(message)
            message_dict.update(media_dict)

            # Get chat information
            chat_dict = self._parse_chat_info(message)
            message_dict.update(chat_dict)

        return message_dict


    def _parse_service_message(self, message):
        """
        Parse a service message into a structured list of dictionaries.

        Service messages include events like new members joining or members leaving
        the chat. Each returned dictionary combines the event metadata, chat info,
        and individual member details.

        Parameters
        ----------
        message : pyrogram.types.Message
            A Pyrogram message object that represents a service event.

        Returns
        -------
        list of dict
            A list of dictionaries with the following keys:
            - msg_id : int
                ID of the service message.
            - posting_time : datetime.datetime
                Time the service message was posted.
            - type : str
                Type of the service message ('new_members' or 'left_chat_member').
            - chat_id : int
                ID of the chat where the message occurred.
            - chat_name : str
                Name/title of the chat.
            - id : int
                ID of the affected member.
            - is_bot : bool
                True if the member is a bot.
            - username : str
                Username of the member (if any).

        Notes
        -----
        - Returns None for unrecognized service messages.
        - Relies on `_parse_chat_info` and `_parse_new_members` to populate
        the chat and member information consistently.
        """


        if not message.service:
            pass

        service_msg = {
            'msg_id': message.id, 
            'posting_time': message.date,
            'type': None
        }

        chat_dict = self._parse_chat_info(message)

        # Check for new chat members
        if message.new_chat_members:
            service_msg['type'] = 'new_members'
            service_msg['members'] = self._parse_new_members(message.new_chat_members)
        
        # Check for left chat member
        elif message.left_chat_member:
            service_msg['type'] = 'left_chat_member'
            service_msg['members'] = self._parse_new_members([message.left_chat_member])

        else:
            pass            
        
        return {**service_msg, **chat_dict}
    
    def _parse_chat_info(self, message):
        """ 
        Extracts basic information about the chat where a message was sent.

        Parameters
        ----------
        message : pyrogram.types.Message
            A Telegram message object.

        Returns
        -------
        dict
            A dictionary containing:
            - 'chat_id' : int or None
                Unique identifier of the chat.
            - 'chat_name' : str or None
                Name/title of the chat.
        """
        return {
            'chat_id': getattr(message.chat, 'id', None),
            'chat_name': getattr(message.chat, 'title', None)
        }


    def _parse_new_members(self, new_members_list):
        """
        Parses information about new members added to a chat.

        Parameters
        ----------
        new_members_list : list of pyrogram.types.User
            List of user objects representing new members.

        Returns
        -------
        list of dict
            Each dictionary contains:
            - 'id' : int
                Unique identifier of the member.
            - 'is_bot' : bool
                Whether the member is a bot.
            - 'username' : str or None
                Username of the member.
        """
        return [
            {
                'id': member.id,
                'is_bot': member.is_bot,
                'username': member.username
            }
            for member in new_members_list
        ]


    def _get_sender(self, message):
        """
        Extracts sender information from a Telegram message.

        Returns a dictionary with:
        - 'sender': 'user' if message is from a user, 'group' if from a channel/group
        - 'sender_id': numeric ID of the sender (user or chat)
        - 'sender_name': username for users or title for groups/channels

        Notes
        -----
        If the message has neither `from_user` nor `sender_chat`, all values remain None.
        """
        sender_dict = {
            'sender': None,
            'sender_id': None,
            'sender_name': None
        }
        
        # Check if message is from user
        if message.from_user:
            sender_dict['sender'] = 'user'
            sender_dict['sender_id'] = message.from_user.id
            sender_dict['sender_name'] = message.from_user.username
        
        # Check if message is from group/chat
        elif message.sender_chat:
            sender_dict['sender'] = 'group'
            sender_dict['sender_id'] = message.sender_chat.id
            sender_dict['sender_name'] = message.sender_chat.title
        
        return sender_dict

    def _get_forward(self, message):
        """
        Extracts forward information from a Telegram message.

        Returns a dictionary with:
        - 'forward_from': 'user' if forwarded from a user, 'chat' if from a channel/chat, None if not forwarded
        - 'forward_id': ID of the original sender (user or chat), None if not available
        - 'forward_name': username for user or title for chat, None if not available

        Notes
        -----
        - Handles messages forwarded from users, anonymous users (forward_sender_name), and chats.
        - If the message was not forwarded, all fields remain None.
        """

        forward_dict = {
            'forward_from': None,
            'forward_id': None,
            'forward_name': None
        }

        # For the messages that were forwarded from the user.
        if message.forward_from:
            forward_dict['forward_from'] = 'user'
            forward_dict['forward_id'] = message.forward_from.id
            forward_dict['forward_name'] = message.forward_from.username
        
        # For the messages that were forwarded from the user who has hidden their id.
        elif message.forward_sender_name:
            forward_dict['forward_from'] = 'user'
            forward_dict['forward_name'] = message.forward_sender_name
        
        # For the messages that were forwarded from the chat.
        elif message.forward_from_chat:
            forward_dict['forward_from'] = 'chat'
            forward_dict['forward_id'] = message.forward_from_chat.id
            forward_dict['forward_name'] = message.forward_from_chat.title
        
        return forward_dict
    
    def _get_reactions(self, message):
        """
        Parses reaction information from a message.

        Parameters
        ----------
        message : pyrogram.types.Message
            A Telegram message object that may contain reactions.

        Returns
        -------
        tuple of (str or None, int)
            A tuple containing:
            - reactions_list : str or None
                Comma-separated string of reactions in format 'emoji: count', or None if no reactions.
            - reactions_count : int
                Total number of reactions across all emoji types, or 0 if no reactions.

        Notes
        -----
        - Aggregates all reaction types and their counts into a single string.
        - Returns (None, 0) if the message has no reactions.
        """

        
        if message.reactions:
            reactions = message.reactions.reactions
            reactions_list = ', '.join([f'{reaction.emoji}: {reaction.count}' for reaction in reactions])
            reactions_count = sum([reaction.count for reaction in reactions])
            return (reactions_list, reactions_count)
        else:
            return (None, 0)

    def _parse_media(self, message):
        """
        Parses the media content of a Telegram message.

        Returns a dictionary with keys:
        - 'media_type': type of the media (photo, video, audio, document, sticker, poll, web_page, text, etc.)
        - 'file_id': unique file identifier for downloadable media, None if not applicable
        - 'content': text content, caption, poll details, or web page description
        - 'file_name': original filename if available, None otherwise

        Notes
        -----
        - Handles standard media types: photo, animation, video, audio, document, voice, video_note.
        - Handles special media types: web_page, poll, sticker.
        - If the message has no media, sets 'media_type' to 'text' and parses the text content.
        - Uses `_parse_text` and `_parse_polls` to extract text or poll data.
        - Unknown media types are printed for debugging.
        """

        media_dict = {
            'media_type': None,
            'file_id': None,
            'content': None,
            'file_name': None
        }
        
        if message.media:
            media_type = message.media._name_.lower()
            media_dict['media_type'] = media_type
            media_content = getattr(message, media_type)
            
            # Standard media types that could include caption
            if media_type in ['photo', 'animation', 'video', 'audio', 'document', 'voice', 'video_note']:
                media_dict['file_id'] = media_content.file_id
                media_dict['content'] = self._parse_text(message.caption, message.caption_entities)
                if hasattr(media_content, 'file_name'):
                    media_dict['file_name'] = media_content.file_name
            
            # Specific media types
            elif media_type == 'web_page':
                media_dict['content'] = (
                    f'{self._parse_text(message.text, message.entities)}'
                    f' // Quotation from {media_content.site_name}({media_content.url}) - '
                    f'{media_content.title}. {media_content.description}.'
                )
            
            elif media_type == 'poll':
                media_dict['content'] = self._parse_polls(media_content)
            
            elif media_type == 'sticker':
                media_dict['file_id'] = media_content.file_id
                media_dict['content'] = getattr(message, media_type).emoji
            else:
                media_dict['media_type'] = 'unknown'
        
        # Messages that consist only of text
        else:
            media_dict['media_type'] = 'text'
            media_dict['content'] = self._parse_text(message.text, message.entities)
        
        return media_dict

    def _parse_text(self, text, entities):
        """
        Parses text content of a Telegram message, optionally incorporating entity URLs.

        Parameters
        ----------
        text : str
            The raw message text.
        entities : list of MessageEntity
            List of Telegram entities (e.g., links, mentions) associated with the text.

        Returns
        -------
        str
            The parsed text with URLs inserted at the entity positions.

        Notes
        -----
        - Adds URLs from entities into the text at the correct offsets.
        - Accounts for cumulative length changes due to inserted URLs.
        - If no entities are present, returns the original text.
        """

        if not entities:
            return text
        
        add_length = 0
        for ent in entities:
            # Add URL if entity has one
            if ent.url:
                url_position = add_length + ent.offset + ent.length
                text = f'{text[:url_position]} {ent.url} {text[url_position:]}'
                add_length += len(ent.url) + 2
        
        return text

    def _parse_polls(self, poll):
        """
        Parses a Telegram poll message into a structured dictionary.

        Parameters
        ----------
        poll : pyrogram.types.Poll
            Telegram poll object containing question, options, and votes.

        Returns
        -------
        dict
            Dictionary with the following keys:
            - 'id' : str, poll identifier
            - 'question' : str, the poll question text
            - 'options' : list of dicts, each with:
                - 'text' : str, option text
                - 'voter_count' : int, number of votes for this option

        Notes
        -----
        - Extracts all poll options and their vote counts.
        - Useful for storing or analyzing poll data in CSV or JSON.
        """

        poll_dict = {
            'id': None,
            'question': None,
            'options': None
        }
        
        poll_dict['id'] = poll.id
        poll_dict['question'] = poll.question
        # Parse poll options with vote counts
        poll_dict['options'] = [
            {'text': option.text, 'voter_count': option.voter_count} 
            for option in poll.options
        ]
        
        return poll_dict
    
