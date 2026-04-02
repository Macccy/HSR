import os
import re

def generate_spans(text, start_id):
    """生成带有 <span> 标签的文本。"""
    percentages = re.findall(r'(\d+(\.\d+)?)%', text)
    span_ids = []
    
    for i, percentage in enumerate(percentages):
        span_id = f'<span id="a{start_id + i}">&nbsp;</span>'
        span_ids.append(span_id)
        text = text.replace(percentage[0] + '%', span_id, 1)
    
    return text, start_id + len(percentages)

def parse_section(file_path, start_id):
    """解析文件并插入适当的 <span> 标签，仅处理 Level 1 的内容。"""
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    result = ""
    collect = False
    for line in lines:
        if "Level 1" in line:
            # 开始收集 Level 1 的内容
            collect = True
            line = line.replace("Level 1:", "").strip()
            parsed_line, next_id = generate_spans(line, start_id)
            result += parsed_line + "\n"
            start_id = next_id
        elif "Level" in line and collect:
            # 碰到下一个 Level 说明 Level 1 的内容结束
            break
        elif collect:
            # 收集 Level 1 内容
            parsed_line, next_id = generate_spans(line.strip(), start_id)
            result += parsed_line + "\n"
            start_id = next_id
    
    return result.strip(), start_id

def main():
    # 文件夹路径
    skill_data_dir = 'skill_data'
    
    # 解析 skill_data 目录中的文件
    basic_atk_result, next_id = parse_section(os.path.join(skill_data_dir, 'Basic_atk.txt'), 1)
    skill_result, next_id = parse_section(os.path.join(skill_data_dir, 'skill.txt'), next_id)
    ultimate_result, next_id = parse_section(os.path.join(skill_data_dir, 'ultimate.txt'), next_id)
    talent_result, _ = parse_section(os.path.join(skill_data_dir, 'talent.txt'), next_id)
    
    # 输出结果到 all_skill_silder.txt
    with open('all_skill_silder.txt', 'w', encoding='utf-8') as f:
        f.write("Basic atk\n\n")
        f.write(basic_atk_result + "\n\n")
        
        f.write("Skill\n\n")
        f.write(skill_result + "\n\n")
        
        f.write("Ultimate\n\n")
        f.write(ultimate_result + "\n\n")
        
        f.write("Talent\n\n")
        f.write(talent_result + "\n")
    
    # 打印完成消息
    print("complete all_skill_silder")

if __name__ == "__main__":
    main()
