import os, json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from transformers import pipeline

####### loading the data from local folder #######
json_file_path = os.path.join('sec_edgar_filings', 'd738839ds1.htm_chunk.json')
with open(json_file_path, 'r') as file:
    data = json.load(file)
print(type(data))
####### END #######

####### xgen 7b 8k #######
tokenizer = AutoTokenizer.from_pretrained("Salesforce/xgen-7b-8k-base", trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained("Salesforce/xgen-7b-8k-base", torch_dtype=torch.bfloat16)
inputs = tokenizer("The world is", return_tensors="pt")
sample = model.generate(**inputs, max_length=128)
print(tokenizer.decode(sample[0]))

# trying to run the above xgen, but when I run, it gets stuck after saying 
# "Setting `pad_token_id` to `eos_token_id`:50265 for open-end generation"
# ended up with this response: 
# Setting `pad_token_id` to `eos_token_id`:50256 for open-end generation.
# The world is full of people who are not happy with their lives. They are not happy with their jobs, their relationships, their families, their friends, their health, their finances, their appearance, their pasts, their futures, their lives. They are not happy with anything.

# They are not happy with themselves.

# They are not happy with the world.
# They are not happy with the universe.

# They are not happy with life.

# They are not happy with death.

# They are not happy with the past.

# They are not happy with the future.

# They are


####### qwen 1.5 110b 32k #######
# qwen_model = "Qwen/Qwen1.5-110B"
# messages = [
#     {"role": "user", "content": "Who are you?"},
# ]
# pipe = pipeline("text-generation", model="Qwen/Qwen1.5-110B")
# pipe(messages) 


# ####### Mixtral 8x 22B-Instruct 64k #######
# tokenizer = AutoTokenizer.from_pretrained("mistralai/Mixtral-8x22B-Instruct-v0.1")
# model = AutoModelForCausalLM.from_pretrained("mistralai/Mixtral-8x22B-Instruct-v0.1") 

