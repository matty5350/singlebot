# Singlebot

## INTRUDUCTION
This bot can be used for multiple A2S games a Tested List below
- Lifeisfuedal (Allows for connection to database to show extra information such as guild Wealth, Killboard etc)
- Dayz
- 7 Days to die
- Rust
- Conan

It should also work for any Steam based game.

It is also capable of much more then just showing bot presence, it also has a built in chat bot which you can change the bot responses by editing the responses.json file to your needs.
It also has Admin only commands that can be used These are listed below:
```
/lifxclearchannel
Description: Deletes all messages in the current channel.
it will delete as many as it can before rate limitation is hit by discord api

/lifxcleanchannel
Description: Deletes only bot messages in the current channel.

/lifxcleanbotdiscord
Description: Deletes all bot messages from every text channel in the server.

/lifxtogglechatbot
Description: Toggles the global chatbot status between enabled and disabled.
i.e stops it talking

/lifxtogglechannelchatbot
Description: Toggles the chatbot status for the specific channel where the command is used.
i.e stops it talking in the channel

/botmsg "message" "image_url"
Description: ends a custom message and optional image (URL must be a direct link to .png, .jpg, .jpeg, or .gif format) as an embedded message in the current channel. ( this is a admin only command )
message = Message you wish to send
image_url = Image you wish bot to provide in the message

```

This Discord bot relies on A2S steam queries to show Bot Presence Example Below: 

<img width="265" height="96" alt="image" src="https://github.com/user-attachments/assets/bbf15e1e-2689-4da6-ac3d-e76d924d4703" />

Pre Requisites

1) Set up a Bot Application on Discord Developers
 - https://discord.com/developers/applications


