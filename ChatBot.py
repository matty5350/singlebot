import random
import json
import logging
import re
import discord
import os

# Configure logging
logging.basicConfig(level=logging.INFO)

class ChatBot:
    def __init__(self, link_channel_id):
        # Define the default response file path
        self.default_responses_file = 'responses.json'  
        self.responses_file_path = self.default_responses_file
        self.responses = self.load_responses(self.responses_file_path)  # Load default responses on initialization
        self.chatbot_enabled = True  # Global chatbot status
        self.channel_status = {}  # Track channel-specific status (enabled/disabled)
        self.link_channel_id = link_channel_id  # Channel ID for sending links
        logging.info("ChatBot initialized with default responses.")

    def load_responses(self, file_path=None):
        """Load responses from a JSON file, with fallback to the default responses file if loading fails."""
        file_path = file_path or self.default_responses_file
        try:
            with open(file_path, 'r') as f:
                responses = json.load(f)
            logging.info(f"Loaded responses from {file_path}")
            logging.debug(f"Responses structure: {responses}")  # Debugging line
            return responses  # Return as a list of intents
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error loading responses from {file_path}: {e}")
            # Fallback to default responses if there's an error with the provided file
            if file_path == self.default_responses_file:
                logging.warning(f"Falling back to default responses file: {self.default_responses_file}")
                return self.load_responses(self.default_responses_file)  # Retry with default
            else:
                return []  # Return empty if even default loading fails

    async def handle_message(self, message):
        """Handle incoming Discord messages."""
        if message.author.bot:
            logging.info(f"Ignored message from bot: {message.content}")
            return  # Ignore messages from bots

        if message.content.startswith('/'):
            await self.handle_command(message)
            return  # Return after processing the command

        if not self.chatbot_enabled:
            logging.info("Chatbot is globally disabled, ignoring message.")
            return

        channel_status = self.channel_status.get(message.channel.id, True)
        if not channel_status:
            logging.info(f"Chatbot is disabled in channel: {message.channel.name}, ignoring message.")
            return

        logging.info(f"Handling message from {message.author}: {message.content}")
        response = self.get_response(message.content)

        if response is not None:
            if isinstance(response, dict):
                embed = discord.Embed(description=response.get("text", ""), color=discord.Color.blue())
                if response.get("image"):
                    embed.set_image(url=response["image"])
                await message.channel.send(embed=embed)
            else:
                await message.channel.send(str(response))

    def get_response(self, user_input):
        """Get a random response based on user input."""
        user_input = user_input.lower()  # Normalize user input to lowercase
        logging.debug(f"User input received: {user_input}")  # Log user input

        if not isinstance(self.responses, list):
            logging.error("Responses is not a list, received: {}".format(type(self.responses)))
            return "I'm currently unable to respond."

        # Check for matches in the responses list
        for item in self.responses:
            if isinstance(item, dict) and 'intent' in item and 'responses' in item:
                # Check regex patterns
                for pattern in item.get("regex", []):
                    if re.search(pattern, user_input, re.IGNORECASE):  # Case-insensitive matching
                        responses = item['responses']
                        if responses:
                            choice = random.choice(responses)
                            # Support both dict with text/image and legacy string responses
                            if isinstance(choice, dict):
                                text = choice.get("text", "I don't have a response for that.")
                                image = choice.get("image")  # Can be None
                                logging.info(
                                    f"Matched pattern: {pattern} for intent: {item['intent']}, response: {text}, image: {image}"
                                )
                                return {"text": text, "image": image}
                            else:
                                logging.info(
                                    f"Matched pattern: {pattern} for intent: {item['intent']}, response: {choice}"
                                )
                                return {"text": choice, "image": None}
                        else:
                            return {"text": "I don't have a response for that.", "image": None}

        logging.warning(f"No response found for user input: {user_input}")
        return None

    async def handle_command(self, message):
        """Handle admin commands."""
        if not message.author.guild_permissions.administrator:
            logging.warning(f"User {message.author} does not have permissions to use commands.")
            return  # Ignore if the user is not an admin

        command = message.content.split(' ', 1)

        if command[0] == '/CBclearchannel':
            await message.channel.purge()
            logging.info(f"CorevionBot Cleared all messages in channel: {message.channel.name}")

        elif command[0] == '/CBcleanchannel':
            await message.channel.purge(limit=None, check=lambda m: m.author.bot)
            logging.info(f"CorevionBot Cleared bot messages in channel: {message.channel.name}")

        elif command[0] == '/CBcleanbotdiscord':
            for channel in message.guild.text_channels:
                await channel.purge(limit=None, check=lambda m: m.author.bot)
            logging.info("CorevionBot Cleared all bot messages from the server.")

        elif command[0] == '/CBtogglechatbot':
            self.chatbot_enabled = not self.chatbot_enabled
            response = "I have woken up" if self.chatbot_enabled else "Preparing to sleep..."
            await message.channel.send(response)
            logging.info(f"CorevionBot status changed: {self.chatbot_enabled}")

        elif command[0] == '/CBtogglechannelchatbot':
            channel_status = self.channel_status.get(message.channel.id, True)
            self.channel_status[message.channel.id] = not channel_status
            response = "I am now active in this channel" if not channel_status else "I have been asked to ignore this channel"
            await message.channel.send(response)
            logging.info(f"CorevionBot Channel status changed for {message.channel.name}: {self.channel_status[message.channel.id]}")

        elif command[0] == '/botmsg':
            # Extract the message and optional image URL using regex
            if len(command) > 1:  # Ensure there are parameters after the command
                match = re.match(r'"(.*?)"(?:\s"(.*?)")?', command[1], re.DOTALL)

                if match:
                    message_content = match.group(1).strip()
                    image_url = match.group(2).strip() if match.group(2) else None

                    # Create an embed with the message content
                    embed = discord.Embed(description=message_content, color=discord.Color.blue())

                    # Validate the image URL if provided
                    if image_url:
                        if re.match(r'^(https?:\/\/|http?:\/\/).*?\.(png|jpg|jpeg|gif)$', image_url, re.IGNORECASE):
                            # If the URL is valid, set it as the image
                            embed.set_image(url=image_url)
                        else:
                            # If the URL is invalid, notify the user
                            await message.channel.send("Error: Invalid image URL. Please provide a direct link to an image with one of the following extensions: `.png`, `.jpg`, `.jpeg`, `.gif`.")
                            logging.warning(f"Invalid image URL provided by {message.author}: {image_url}")
                            return  # Exit after sending the error message
                    else:
                        logging.info(f"No image URL provided by {message.author}")

                    # Send the embed to the channel
                    await message.channel.send(embed=embed)
                    logging.info(f"Sent bot message: {message_content}, with image: {image_url if image_url else 'No image'}")
                    
                    # Delete the original command message
                    await message.delete()
                    logging.info(f"Deleted command message from {message.author}")

                else:
                    await message.channel.send("Error: Please provide the message in quotes.")
                    logging.error("Failed to parse the !botmsg command.")
            else:
                await message.channel.send("Error: Please provide the message in quotes.")
                logging.error("No message provided for !botmsg command.")

    async def change_responses_file(self, file_name):
        """Change the response file used for chatbot responses based on the selected file."""
        # Construct the file path for the selected response file
        if file_name == "CBmodding":
            new_file_path = os.path.join("modding", "responses_CBmodding.json")
            
        elif file_name == "honeypot":
            new_file_path = os.path.join("ServerRelatedResponses", "responses_honeypot.json")
            
        elif file_name == "newland":
            new_file_path = os.path.join("ServerRelatedResponses", "responses_newland.json")
            
        elif file_name == "vikings":
            new_file_path = os.path.join("ServerRelatedResponses", "responses_vikings.json")
        else:
            new_file_path = os.path.join("GameRelatedResponses", f"responses_{file_name}.json")

        logging.debug(f"Attempting to load responses from {new_file_path}")

        # Clear previous responses before loading new ones
        self.responses.clear()  # Clear any existing responses

        self.responses = self.load_responses(new_file_path)
        if self.responses:
            self.responses_file_path = new_file_path
            logging.info(f"Responses file changed to {new_file_path}")
            return True
        else:
            logging.error(f"Failed to load responses from {new_file_path}")
            return False

# Initialize the bot
bot = discord.Client(intents=discord.Intents.default())
CB_bot = ChatBot(link_channel_id=1234567890)  # Replace with your actual link channel ID

@bot.event
async def on_ready():
    logging.info(f"Bot logged in as {bot.user}")

@bot.event
async def on_message(message):
    await CB_bot.handle_message(message)
