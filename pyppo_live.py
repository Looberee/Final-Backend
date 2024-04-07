from flask import Flask, jsonify, request, redirect
from discord.ext import commands
import discord  # Add this line
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import asyncio
import requests
from urllib.parse import urlencode
import threading

app = Flask(__name__)
intents = discord.Intents.default()
# Initialize the Discord bot
pyppo_bot = commands.Bot(command_prefix='!', intents=intents)
pyppo_token = 'MTIyNjQ5Nzk1NzE3MjM0Njk0MQ.GApILx.O4hBAGwdEn_Q2i3-w09RQPgLYmTRzLLY0ACC8g'
discord_auth = {
    'client_id': '1226497957172346941',
    'client_secret': 'UA6DjTjHQdhllFYoiuVk7RsoE_C19cMR',
    'redirect_uri': 'http://127.0.0.1:5001/callback',
}
# Command to play a track from Spotify
@pyppo_bot.command()
async def pchat(ctx):
    # Send a message to the Discord channel
    await ctx.send("Hello, I am pyppo_bot!")
    
@pyppo_bot.command()
async def pla(ctx):
    # Send a message to the Discord channel
    await ctx.send("What do you mean dude?")

# Start the Flask server in a separate thread
async def start_flask_server():
    await pyppo_bot.wait_until_ready()  # Wait for the pyppo_bot to be ready
    app.run(debug = True,port=5001)  # Start Flask server
        
async def main():
    # Create tasks for the bot and the Flask server
    bot_task = asyncio.create_task(pyppo_bot.start(pyppo_token))
    flask_task = asyncio.create_task(start_flask_server())

    # Run the tasks concurrently
    await asyncio.gather(bot_task, flask_task)

@app.route('/authorize')
def authorize():
    params = {
        'client_id': discord_auth['client_id'],
        'redirect_uri': 'http://127.0.0.1:5001/callback',
        'response_type': 'code',
        'scope': 'bot connections'
    }

    url = 'https://discord.com/api/oauth2/authorize?' + urlencode(params)

    return redirect(url)


@app.route('/callback')    
def callback():
    code = request.args.get('code')
    
    # Check if the code is None
    if code is None:
        error = request.args.get('error')
        return jsonify({'error': error}), 400
    
    # Prepare data for the token request
    data = {
        'client_id': discord_auth['client_id'],
        'client_secret': discord_auth['client_secret'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'http://127.0.0.1:5001/callback',
        'scope': 'bot connections'
    }
    
    # URL encode the data
    data = urlencode(data)
    
    # Send a POST request to the Discord token endpoint
    response = requests.post('https://discord.com/api/oauth2/token', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    
    # Get the access token from the response
    access_token = response.json().get('access_token')
    info = response.json()

    return jsonify({"message" : "Callback received", "access_token" : access_token, "data" : data, "info": info})

# Start the pyppo_bot and Flask server concurrently
if __name__ == "__main__":
    pyppo_bot.run(pyppo_token)
    asyncio.run(main())
