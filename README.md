# Corevion Bot

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
/CBclearchannel
Description: Deletes all messages in the current channel.
it will delete as many as it can before rate limitation is hit by discord api

/CBcleanchannel
Description: Deletes only bot messages in the current channel.

/CBcleanbotdiscord
Description: Deletes all bot messages from every text channel in the server.

/CBtogglechatbot
Description: Toggles the global chatbot status between enabled and disabled.
i.e stops it talking

/CBtogglechannelchatbot
Description: Toggles the chatbot status for the specific channel where the command is used.
i.e stops it talking in the channel

/botmsg "message" "image_url"
Description: Sends a custom message and optional image (URL must be a direct link to .png, .jpg, .jpeg, or .gif format) as an embedded message in the current channel. ( this is a admin only command )
message = Message you wish to send
image_url = Image you wish bot to provide in the message

```

This Discord bot relies on A2S steam queries to show Bot Presence Example Below: 

<img width="265" height="96" alt="image" src="https://github.com/user-attachments/assets/bbf15e1e-2689-4da6-ac3d-e76d924d4703" />

## Pre Requisites

1) Set up a Bot Application on Discord Developers
 - https://discord.com/developers/applications

 You need this to gain a Bot ID for the setup process

2) A bot Hosting Requirement
- It is reccomended to use https://rampart.games/store/bot-hosting for hosting the bot.
  - As It is not expensive and is also Stable
- Using Docker Image Python 3.12 (As Pictured)
<img width="1475" height="915" alt="image" src="https://github.com/user-attachments/assets/29c98851-d1fc-428d-9590-56ce9c96d749" />


## INSTALLATION
1) Upload all files to your hosting
2) inside the Bots folder, a file exists named bot.json
 - under the variable "bot_token" place your bot token provided by Discord Developer portal here inside the ""
3) In the same file Set the channel ids for the variables:
   server_status
   server_rules
   killboard (only for life is fuedal)
   guildwealth (only for life is fuedal)
   Ensure the "enabled" and "update_enabled" Variables are set to true or false dependant on your requirements.

4) Ensure all other fields are filled in for this file, based on your game server.
Please not db information  is only required for life is fuedal Guild wealth and killboard

5) Amend the responses.json file which is located in route directory to your requirements
6) On the Startup section of Ramparts hosting set the "APP PY FILE" field to bot.py
7) On the Startup section of Ramparts hosting set the "Requirements file" field to requirements.txt
As pictured below
<img width="1730" height="903" alt="image" src="https://github.com/user-attachments/assets/c0140415-6602-46ef-86e8-7a29542a6407" />
8) Click Console and then click start
- Assuming you have set up the Discord Developer permissions correctly for the app it should start up
- ALSO FOR THE BOT TO WORK CORRECTLY YOU MUST INVITE YOUR DISCORD BOT TO YOUR DISCORD




