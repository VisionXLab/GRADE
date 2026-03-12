from consis import consis_eval
from reasoning import reasoning_eval
from read import read_eval
from sum import score_sum
import json, os

#========config=============
data_json =  "/path/to/your/result.json"  #xxx/model name/result.json; the generated intermediate files will be saved in the root directory of the JSON.
BASE_URL = ""
API_KEY = "" 
WORKERS = 20  #Parallel evaluation count
#============================

#======default config========
judge = "gemini-3-flash-preview"
judge_reasoning = "gemini-3-flash-preview"
non_pass_list = []
name_pro = {
    "gemini-3-flash-preview": ["gemini-3-flash-preview", "gemini_flash"] 
  }
#============================

API_CONFIG = {
  "url": BASE_URL,
  "key": API_KEY
}
result_folder_list = reasoning_eval(data_json, name_pro[judge_reasoning], non_pass_list, API_CONFIG, WORKERS)

consis_folder = consis_eval(data_json, name_pro[judge], non_pass_list, API_CONFIG, WORKERS)
result_folder_list.append(consis_folder)

read_folder =  read_eval(data_json, name_pro[judge], non_pass_list, API_CONFIG, WORKERS)
result_folder_list.append(read_folder)

print(result_folder_list)
for folder in result_folder_list:
  dir_name = os.path.dirname(folder)
  folder_name = folder.split('/')[-1]
  merge_file = os.path.join(dir_name, f"{folder_name}.json")
  merge_datas = []
  for dir_n, _, files in os.walk(folder):
    for file in files:
      if file.split('.')[-1] == "json":
        with open(os.path.join(dir_n, file), 'r', encoding='utf-8') as f:
          data = json.load(f)
        merge_datas.append(data)
  with open(merge_file, 'w', encoding='utf-8') as f:
    json.dump(merge_datas, f, indent=4, ensure_ascii=False)
  print("save file: ", merge_file, ": )")

#==score calculation======
score_sum(os.path.dirname(data_json))