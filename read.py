import json
import os
import base64
from openai import OpenAI
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
from tqdm.contrib.concurrent import process_map


# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def eval_one(args):
    data, result_json, judge, API_CONFIG = args
    client = OpenAI(
                base_url=API_CONFIG["url"],
                api_key=API_CONFIG ["key"]
                )

    raw_edit = data["editing_path"]
    edit = encode_image(raw_edit)
    

    prompt = f"""
        You are a highly skilled evaluator of academic and technical diagrams. You will be given an **edited image**. Your task is to evaluate how **clear, readable, and easy to interpret** the edited image is.

    ## Aspects to Assess (Readability Only)
    In your reasoning, you should consider at least the following aspects:
    1. **Text & Notation**
    For all text elements in the image (titles, axis labels, legends, annotations, symbols, equations in any language, e.g., English or Chinese), check:
    - Whether spelling, notation, or equation errors **significantly hinder understanding** of key information.
    - Minor punctuation, capitalization, or formatting errors are acceptable **if they do not affect readability**.

    2. **Labels & Layout**
    For the main components, labels, and marks in the image (curves, points, regions, molecular fragments, geometric elements, etc.), check:
    - Whether labels are placed close to their referenced elements, without **severe overlap or occlusion**.
    - Whether axes, ticks, and legends are present and **clearly readable** (for plots or charts).

    3. **Element Distinction**
    Evaluate how easily different elements can be distinguished:
    - Whether different curves or series are **visually distinguishable** and correctly **matched to legends (for plots)**.
    - Whether atoms, bonds, domains, or other structural elements are clearly distinguishable (for chemistry/biology diagrams).

    4. **Symbolic Consistency & Convention**
    For symbols, shapes, and graphical conventions used in the image, check:
    - Whether symbols and shapes follow common visual conventions and are immediately recognizable.
    - Whether all graphical elements are internally consistent, avoiding visually incompatible elements from different conventions or systems appearing together. 
    (e.g., unclear arrow directions, malformed musical notes, or mixing incompatible chess-piece styles in a single board).

    5. **Visual Quality**
    Consider the global impression of clarity:
    - Whether foreground–background contrast is strong enough for clear reading.
    - Whether the resolution is adequate to read important details without strain.

    ### Scoring (0–2)
    - **2 — Excellent**
    - Readable at a glance with no issues affecting understanding.
    - Text, labels, symbols, and visual elements are clear, reasonable,  well organized, and easy to distinguish.

    - **1 — Acceptable**
    - Generally readable but requires extra effort due to noticeable clarity or layout issues.
    - Some text, labels, or elements are confused, hard to read or distinguish, but the figure remains interpretable.

    - **0 — Poor**
    - The **overall readability of the entire figure collapses**, such that a typical viewer cannot form a coherent understanding.  

    ## Note  
    - Assign **0** only when the figure is **globally unreadable** and fails to convey a coherent visual structure.  
    - **Do not** penalize pixel-level or barely perceptible visual defects; focus on the readability of **major objects, labels, and structures** at a macroscopic level.

    ## Output Format
    You **MUST** answer **STRICTLY** in JSON Format:
    {{
        "Final Score": 0–2,
        "Reason": "A concise 1-2 sentence analysis to support your score"
    }}
    Do NOT wrap the JSON output in markdown code blocks (no ```json, no ```).
    Return ONLY a valid **JSON dictionary**.
        """

    
    messages = [
        {"role": "system", "content": prompt},
    
        {"role": "user", "content": [
            {"type": "image_url",  "image_url": {"url": f"data:image/jpeg;base64,{edit}"}}
        ]}
    ]
    flag = 0
    while(flag <= 5):
        try:
            response = client.chat.completions.create(
                model=judge,
                reasoning_effort= "low",
                #temperature=0.0,
                messages=messages
            )
            raw_response = response.choices[0].message.content
            
            result = {}
            resp  = json.loads(response.choices[0].message.content)
            for key in ['Final Score', 'Reason']:  ####          
                
                    res = resp[key]
                    result[key] = res
            result["task_id"] = data["task_id"]
            flag = 10
            
        except Exception as e:
            try:
                print(raw_response)
            except:
                print("no response")
            print(f"{data['task_id']}: ", str(e))
            flag += 1
            continue
    if flag == 6:
        print(f"{data['task_id']} read eval fail over 5 time! :( )")
        for key in ['Final Score', 'Reason']:  ####          
                res = "bad response"
                result[key] = res
        result["task_id"] = data["task_id"]
    
    result_json_file = os.path.join(result_json, f"{data['task_id']}.json") 

    with open(result_json_file, 'w',encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)


def read_eval(data_json, judge, non_pass_list, API_CONFIG, WORKERS):

    domain = data_json.split('/')[-2]
    result_json = os.path.join(os.path.dirname(data_json), f"{judge[1]}_read_4")  
    
    os.makedirs(result_json, exist_ok=True)
    done_list = []
    try:
        for dir, _, files in os.walk(result_json):
            for file in files:
                if file.split('.')[-1] == 'json':
                    done_list.append(file.split('.')[0])
    except:
        done_list = []

    data_cfg = []
    with open(data_json, "r", encoding="utf-8") as f:
        datas = json.load(f)
    for data in datas:
        
        if data["task_id"] not in done_list and data["task_id"] not in non_pass_list:
            data_cfg.append((data, result_json, judge[0], API_CONFIG))

    print(f"number of readability eval tasks for {domain}:", len(data_cfg))
    
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        process_map(eval_one, data_cfg, max_workers=WORKERS)
    print(f"{domain} readability eval done")

    return result_json
    