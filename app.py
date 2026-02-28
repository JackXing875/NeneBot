import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

# 1. 设定模型路径（联网自动下载基座，本地加载宁宁的灵魂）
BASE_MODEL = "qwen/Qwen2.5-7B-Instruct" 
LORA_PATH = "./nene_lora_weights" # 你训练出来的几十MB文件夹

print("正在唤醒宁宁，请稍候...")
# 2. 加载分词器和基座模型 (使用 4-bit 量化加载以适配普通显卡)
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    device_map="auto",
    load_in_4bit=True # 确保 clone 你项目的人也能在 8GB 显卡上跑
)

# 3. 灵魂注入：将你的 LoRA 权重与基座合并
model = PeftModel.from_pretrained(base_model, LORA_PATH)

# 4. 定义对话生成逻辑
def chat_with_nene(message, history):
    # 注入宁宁的 System Prompt
    messages = [{"role": "system", "content": "你现在是《魔女的夜宴》中的绫地宁宁。你性格温柔负责，有些傲娇..."}]
    
    # 拼接历史对话
    for user_msg, bot_msg in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": bot_msg})
        
    messages.append({"role": "user", "content": message})
    
    # 转换格式并生成回复
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    generated_ids = model.generate(model_inputs.input_ids, max_new_tokens=512, temperature=0.7)
    generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
    
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return response

# 5. 启动 Gradio 聊天网页
demo = gr.ChatInterface(
    fn=chat_with_nene,
    title="绫地宁宁 Cyber-Bot ☕",
    description="《魔女的夜宴》绫地宁宁专属对话大模型。基于 Qwen2.5-7B 微调。",
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)