import json
import os

# ================= 配置区 =================
INPUT_DIR = "/home/schrieffer/NeneBot/data/raw"               # 把所有的 txt 文件都放在这个目录下
OUTPUT_FILE = "/home/schrieffer/NeneBot/data/processed/nene_finetune.jsonl"  # 最终输出的语料文件

# 强力的系统提示词
SYSTEM_PROMPT = "你现在是《魔女的夜宴》中的绫地宁宁。你性格温柔负责，平时是图书委员，但隐瞒着魔女的身份。面对喜欢的人会有些傲娇和口是心非。请用符合绫地宁宁的语气进行回复。"

USER_NAMES = ["柊史", "保科柊史", "男主"]
ASSISTANT_NAMES = ["宁宁", "绫地宁宁", "綾地寧々"]
# ==========================================

def process_all_scripts():
    dataset = []
    total_files = 0
    
    # 检查输入文件夹是否存在
    if not os.path.exists(INPUT_DIR):
        print(f"请先创建 {INPUT_DIR} 文件夹，并放入 txt 剧本文件！")
        return

    # 遍历目录下的所有 txt 文件
    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith('.txt'):
            continue
            
        filepath = os.path.join(INPUT_DIR, filename)
        total_files += 1
        print(f"正在处理文件: {filename} ...")
        
        # 每个文件开始时，重置状态机，避免跨文件上下文污染
        current_speaker = None
        last_user_text = None
        
        lines = []
        # 按优先级尝试常见的编码格式（gb18030 是 gbk 的超集，非常适合读汉化组的文本）
        for enc in ['utf-8', 'gb18030', 'shift_jis']:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    lines = f.readlines()
                print(f"  -> 成功使用 {enc} 编码解析。")
                break
            except UnicodeDecodeError:
                continue
                
        if not lines:
            print(f"  -> [报错] 穷尽了所有常见编码，仍无法读取 {filename}，请检查文件是否损坏！")
            continue

        for line in lines:
            line = line.strip()
            
            if line.startswith(';['):
                parts = line.split(']', 1)
                if len(parts) < 2: 
                    continue
                    
                content = parts[1].strip()
                if not content: 
                    continue
                
                # 状态机逻辑
                if content in USER_NAMES or content in ASSISTANT_NAMES:
                    current_speaker = content
                    
                elif content.startswith('「') and content.endswith('」'):
                    dialogue = content.strip('「」')
                    
                    if current_speaker in USER_NAMES:
                        last_user_text = dialogue
                        
                    elif current_speaker in ASSISTANT_NAMES:
                        if last_user_text:
                            dataset.append({
                                "messages": [
                                    {"role": "system", "content": SYSTEM_PROMPT},
                                    {"role": "user", "content": last_user_text},
                                    {"role": "assistant", "content": dialogue}
                                ]
                            })
                            last_user_text = None 
                else:
                    current_speaker = None

    # 写入最终的 JSONL
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for data in dataset:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')
            
    print(f"🎉 提取完成！共读取了 {total_files} 个文件，挖掘出 {len(dataset)} 轮高质量的宁宁对话。")

if __name__ == "__main__":
    process_all_scripts()