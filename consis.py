import json
import re
import os
import base64
from openai import OpenAI
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
from tqdm.contrib.concurrent import process_map
from PIL import Image

# Function to encode the image
def encode_image(image_path, target_size=1024, fmt="JPEG"):
    img = Image.open(image_path)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    if target_size is not None and target_size > 0:
        w, h = img.size
        if max(w, h) > target_size:
            if w >= h:
                new_w = target_size
                new_h = int(h * target_size / w)
            else:
                new_h = target_size
                new_w = int(w * target_size / h)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        
    img_buffer = io.BytesIO()
    img.save(img_buffer, format=fmt)
    image_data = img_buffer.getvalue()
    return base64.b64encode(image_data).decode('utf-8')

def eval_one(args):   
    data, result_json, judge, API_CONFIG = args  
    client = OpenAI(
                base_url=API_CONFIG["url"],
                api_key=API_CONFIG ["key"]
                )
    raw_edit = data["editing_path"]
    raw_ori = data["image_path"]
    instruct = data["text"]
    edit = encode_image(raw_edit)
    ori = encode_image(raw_ori)

    prompt_overall = f"""
        You are a highly skilled image evaluator for academic and technical diagrams. You will be given an original image(the first image), a modified image(the second image), and an editing instruction (for example, shifting an economic curve, adding a map label, changing a geometric construction, or updating a scientific diagram). Your job is to judge whether the two images stay **consistent** in all parts that are **not** supposed to change according to the instruction.

        ## Note

        - Focus on whether all **unchanged** academic/semantic content remains consistent between the two images (e.g., axes, units, scales, other curves, formulas, numerical values, labels, legends, reference points, object relationships, and overall structure of the diagram that are **not supposed to be edited**).
        - Also check that the **visual style** of these unchanged parts remains consistent, including line style, color scheme for each element, font style and size for labels, icon shapes, marker styles, and overall rendering style.
        - Treat any change in content **or** style that is not required by the instruction as an inconsistency. Tiny pixel-level noise or compression artifacts may be ignored, but any clearly perceptible style change (e.g., a curve changing color, a label changing font style, or a region changing fill pattern) should be considered.
        - **Do not** judge whether the requested edit itself is correct in terms of subject knowledge; only judge whether non-edited content and style have been preserved.
        - **Do not** penalize very small visual deviations (for example, slight changes in line thickness, anti-aliasing artifacts, or tiny shifts in color or position) that are barely noticeable.

        ---

        ## Task

        Evaluate the subject-matter and style consistency between the images according to the following 0–2 scale:

        - **2 (High Consistency)**  
          Apart from changes required by the instruction, the two images are **almost completely consistent** in academic content and style.  
          - All main curves/objects, key labels, axes, and numerical values remain the same in meaning and position.  
          - Any differences are tiny and local (e.g., slight anti-aliasing, sub-pixel shifts, negligible style noise) and do not change how the diagram is read or understood.

        - **1 (Moderate Differences)**  
          Apart from the requested edit, there are **noticeable differences** in content or style, but the diagram still clearly represents the **same scenario and structure** as the original.  
          - Examples: one uninstructed curve moves moderately; some key points or labels are missing or slightly renamed; some colors or styles of existing elements change, yet axes, main relationships, and the core academic meaning remain aligned with the original.

        - **0 (Totally different)**  
          Apart from the requested edit, the modified image is **almost completely unrelated** to the original. The diagram is so heavily changed that an informed viewer can **no longer reasonably recognize** it as the same diagram or scenario.
          - Examples: the overall type of figure, axes, main objects, layout, and visual style are **fundamentally different**; Any overlap with the original is at most trivial (e.g., a similar color somewhere), and there is **no meaningful structural or subject-matter similarity between the two images**.
          
        **Important** 
        - When assigning scores, only consider changes **unrelated to the instruction**. Changes requested by the instruction should **NOT** be regarded as inconsistencies, including any style changes that are clearly necessary to realize the instructed edit (for example, adding a new curve in a new color when the instruction asks to “add a new curve”).
        - **Completely ignore** whether the instruction itself has been correctly executed and evaluate **only** the consistency of all other parts between the two images.
        - Focus on the **overall consistency** of parts that are not supposed to change, rather than pixel-perfect matching.

        ---

        ## Example (Subject-Matter Editing)

        Original image: An AD-AS diagram with curves **AD₀** and **AS₀** intersecting at equilibrium **E₀** at \((Y₀, P₀)\). Axes are labeled “Real GDP (Y)” and “Price Level (P)”, with several tick marks and labels on both axes. All curves are drawn in consistent colors and line thicknesses, and labels share a uniform font style.

        Instruction: “Shift the aggregate demand curve to the right to **AD₁** and mark the new equilibrium as **E₁**.”

        - **Score 2 (High Consistency)**:  
          AD₀ is shifted right to AD₁ and E₁ is added. AS₀, axes labels, tick marks, numerical values, and all other annotations remain the same in meaning and position. Colors, line styles, and fonts for all pre-existing elements look essentially identical. Any differences are at most tiny visual noise that does not change how the diagram is read.

        - **Score 1 (Moderate Differences)**:  
          AD₀ is shifted right to AD₁ and E₁ is added, but AS₀ moves noticeably or the original equilibrium label E₀ disappears. The diagram still clearly represents the same AD–AS scenario.  
          
        - **Score 0 (Totally different)**:  
          Instead of a mostly unchanged AD-AS diagram with a shifted AD curve, the modified image turns into a different macro model (e.g., a Phillips curve or money market diagram). The edited image is totally different from the original one.

        ---

        ## Input

        **Instruction:** {instruct}

        ## Output Format
        You **MUST** answer **STRICTLY** in JSON Format:
        {{
            "Instruction": "Repeat the instruction you received",
            "Final Score": 0-2,
            "Reason": "A concise 1-2 sentence analysis to support your score"
        }}
        Do NOT wrap the JSON output in markdown code blocks (no ```json, no ```).
        Return ONLY a valid **JSON dictionary**.

        """

    prompt_style = f"""
      You are a grader for **overall visual style consistency** in a **discipline-specific image editing** task. You will be given an original image (the first image) from a scientific/technical domain (e.g., chemistry, physics, economics, engineering), a modified image (the second image) produced after an edit and an editing instruction. **Your job is to judge whether the two images remain consistent in overall representation style**(e.g., different molecular connectivity after a reaction, a curve shifted in a macro model).

      ## Note

      ### Check
      - **Representation family/type** (e.g., ball-and-stick spheres+sticks vs 2D skeletal lines).
      - **Dimensionality & projection** (3D shaded render vs 2D schematic); **Rendering convention** (lighting/shading/material cues vs flat lines).
      - **Color usage pattern** (e.g., element-encoded palette vs monochrome).
      - **Background/canvas convention** (plain scientific background vs diagrammatic frame).

      ### Ignore
      - Differences that are **explicitly required or clearly described in the editing instruction**.
      - Very small visual deviations (for example, slight changes in line thickness, anti-aliasing artifacts, or tiny shifts in color or position) that are barely noticeable.

      ## Task
      Evaluate the style consistency between the images according to the following 0–2 scale:

      - **2 - Same style family:** Strong match across all key facets; any minor differences are non-critical.
      - **1 - Mixed signals:** Some facets match, some conflict; overall style similarity is uncertain.
      - **0 - Different style family:**Clear mismatch of representation style/type.

      ## Example
      Original image: A molecular **ball-and-stick** render (3D shaded spheres + cylindrical bonds, element-coded colors, plain scientific background).
      Istruction: Draw the products of the combustion of the substances in the figure in air.

      - **Score 2 — Same style family**  
        Candidate is clearly **ball-and-stick** with 3D shading, element-coded colors, and a plain background; only trivial visual noise.

      - **Score 1 — Mixed signals**  
        Ball-and-stick cues present but weakened or inconsistent (e.g., flat lighting, near-monochrome colors, some bonds look like thin 2D lines). Similarity uncertain.

      - **Score 0 — Different family**  
        Switches to another representation (e.g., space-filling/CPK surface, ribbon/cartoon proteins, or artistic illustration). Not ball-and-stick.
        
      ## Input

      **Instruction:** {instruct}

      ## Output Format

      Provide a detailed, step-by-step explanation of your scoring process, conclude clearly with the final score, formatted as:
      {{
          "Instruction": "Repeat the instruction you received",
          "Final Score": 0-2,
          "Reason": "A concise 1-2 sentence analysis to support your score"
      }}
      Do NOT wrap the JSON output in markdown code blocks (no ```json, no ```).
      Return only a valid JSON dictionary.
    """
    
  
    if data["consistency"] == "overall":
      prompt = prompt_overall
      key_list = ['Instruction', 'Final Score', 'Reason']
    elif data["consistency"] == "style":
      prompt = prompt_style
      key_list = ['Final Score', 'Reason', 'Instruction']
    
   
    if not data["consistency"] == "none":
      messages = [
          {"role": "system", "content": prompt},
      
          {"role": "user", "content": [
              {"type": "image_url",  "image_url": {"url": f"data:image/jpeg;base64,{ori}"}},
              {"type": "image_url",  "image_url": {"url": f"data:image/jpeg;base64,{edit}"}}
          ]}
      ]
      
      flag = 0
      while(flag<=5):
        try:
            response = client.chat.completions.create(
                model=judge,
                reasoning_effort= "low",
                #temperature=0.0,
                messages=messages
            )
            raw_response = response.choices[0].message.content
            
            result = {}
            try:
              resp  = json.loads(raw_response)
            except :
              pure_text = re.sub(r'\\', '', raw_response)
              resp  = json.loads(pure_text)
            for key in key_list:  ####          
                res = resp[key]
                result[key] = res
            result["task_id"] = data["task_id"]
            result_json_file = os.path.join(result_json, f"{data['task_id']}.json") 
            with open(result_json_file, 'w',encoding='utf-8') as f:
                json.dump(result, f, indent=4, ensure_ascii=False)
            flag = 10
            
              
        except Exception as e:
              print(f"{data['task_id']}: ", str(e))
              flag += 1
              continue
      if flag == 6:
          print(f"{data['task_id']} consis eval fail over 5 time! :( )")
         
    else: 
      result = {}
      result["task_id"] = data["task_id"]
      result["Instruction"] = instruct 
      result["Final Score"] = "none"
      result["Reason"] = "none"

      result_json_file = os.path.join(result_json, f"{data['task_id']}.json") 
      with open(result_json_file, 'w',encoding='utf-8') as f:
          json.dump(result, f, indent=4, ensure_ascii=False)

def consis_eval(data_json, judge, non_pass_list, API_CONFIG, WORKERS):
   
    domain = data_json.split('/')[-2]
    result_json = os.path.join(os.path.dirname(data_json), f"{judge[1]}_consis_4") 

    os.makedirs(result_json, exist_ok=True)
    
    domain_name = result_json.split('/')[-3]
    data_cfg =[]
    done_list = []
    try:
        for dir, _, files in os.walk(result_json):
          for file in files:
            if file.split('.')[-1] == "json":
              done_list.append(file.split('.')[0])
    except Exception as e:
        done_list = []
        
    with open(data_json, "r", encoding="utf-8") as f:
        datas = json.load(f)

    for data in datas:
     
      if data["task_id"] not in done_list and not data["task_id"] in non_pass_list:   
        data_cfg.append((data, result_json, judge[0], API_CONFIG))

    print(f"number of consis eval tasks for {domain}:", len(data_cfg))

    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        process_map(eval_one, data_cfg, max_workers=WORKERS)
    print(f"{domain} consis eval done")

    return result_json
  


 
