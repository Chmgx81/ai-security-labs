# Allows the script to read your evironment variables
import os

# bring in Mistral's official library
from mistralai.client import Mistral
 
 # the door to their servers. It silently reads $MISTRAL_API_KEY from your environment — that's why we stored it with set -Ux. Zero keys in this file.
client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

# end the request: model = which brain, messages = the conversation, role: "user" = that's you talking
response = client.chat.complete(
    model="mistral-small-latest",
    messages=[
        {"role": "user", "content": "Say exactly this: hello from my first AI script"}
    ],

)

# the reply comes wrapped in layers (choices → message → content). This unwraps it down to the plain text
print(response.choices[0].message.content)