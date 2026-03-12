import json
import os


def score_sum(root):
    single_scoredic = {}
    model = root.split('/')[-1]
    single_scoredic["domain"] = "full set"
    single_scoredic["model"] = model
    reasoning_file = os.path.join(root, "gemini_flash_eval_1.json")
    consis_file = os.path.join(root, "gemini_flash_consis_4.json")
    read_file = os.path.join(root, "gemini_flash_read_4.json")
    full_result_file = os.path.join(root, "full_result_gemini_flash.json") 
    for strategy in ["soft", "hard"]:
        if strategy == "soft":
            reason_score = 0

            with open(reasoning_file, 'r', encoding='utf-8') as f:
                reasoning_datas = json.load(f)
            total_num = len(reasoning_datas)
            consis_num = len(reasoning_datas)
            #print(total_num)
            for data in reasoning_datas:
                reason_score += data["score"] * 100
            reason_score = reason_score/total_num

            consis_score = 0
            with open(consis_file, 'r', encoding='utf-8') as f:
                consis_datas = json.load(f)
            for data in consis_datas:
                if data["Final Score"] == "none":
                    single_score = 0
                    consis_num -= 1
                else:
                    single_score = data["Final Score"]
                consis_score += single_score * 50
            consis_score = consis_score/consis_num

            read_score = 0
            with open(read_file, 'r', encoding='utf-8') as f:
                read_datas = json.load(f)
            for data in read_datas:
                read_score += data["Final Score"] * 50
            read_score = read_score/total_num
            score = 0.6 * reason_score + 0.3 * consis_score + 0.1 * read_score
            
            assert len(read_datas) == len(consis_datas) == len(reasoning_datas), f"unmatched eval number for {task} {model}:\n" + f"reasoning num: {len(reasoning_datas)}\n" + f"consis number: {len(consis_datas)}\n" + f"readability number: {len(read_datas)}\n"
            single_scoredic["total_num"] = len(consis_datas)
            
            
            print(f"final score for full set {model}: \n")
            print("reasoning score: ", reason_score)  
            print('\n') 
            print("consist score: ", consis_score)  
            print('\n') 
            print("readability score: ", read_score)  
            print('\n') 
            print("total relax score: ", score) 
            print('\n')  
            print("consist num: ", consis_num) 
            print('\n')  
            print("total num: ", total_num)
            print('\n')  

            single_scoredic["consis_num"] =  consis_num
            single_scoredic["reasoning score"] =  round(reason_score, ndigits = 1)
            single_scoredic["consist score"] = round(consis_score, ndigits = 1)
            single_scoredic["readability score"] = round(read_score, ndigits = 1)
            single_scoredic["relax_score"] = round(score, ndigits = 1)

        else:
            score = 0
            full_results = []
            for reason_data in reasoning_datas:
                for consis_data in consis_datas:
                    if reason_data["vqa"][0]["id"] == consis_data["task_id"]: #and consis_data["task_id"] in filter_list:
                        for read_data in read_datas:
                            if consis_data["task_id"] == read_data["task_id"]:
                                
                                if reason_data["score"] > 0.99 and (consis_data["Final Score"] == 2 or consis_data["Final Score"] == "none") and read_data["Final Score"] == 2:
                                #if reason_data["score"] > 0.99:
                                    score += 1
                                    acc_score = 1
                                    #print("pass task:", consis_data["task_id"])
                                else:
                                    acc_score = 0
                                    #non_pass.append(reason_data["vqa"][0]["id"])
                                single = {}
                                single["task_id"] = consis_data["task_id"]
                                single["reasoning"] = reason_data
                                single["consis"] = consis_data
                                single["read"] = read_data
                                single["acc_score"] = acc_score
                                if consis_data["Final Score"] == "none":
                                    single["relax_score"] = 0.8 * reason_data["score"] * 100 + 0.2 * read_data["Final Score"]* 50
                                else:
                                    single["relax_score"] = 0.6 * reason_data["score"] * 100 + 0.3 * consis_data["Final Score"]* 50 + 0.1 * read_data["Final Score"] * 50
                                
                                full_results.append(single)
            print("pass num: ", score)
            single_scoredic["pass num"] = score
            score = score / total_num
            single_scoredic["acc_score"] = round(score * 100, ndigits = 1)
            
            
            print(f"final acc score for full set {model}: \n")
            print(score)   
            with open(full_result_file, 'w', encoding='utf-8') as f:
                json.dump(full_results, f, indent=4, ensure_ascii=False)     
    #score_list.append(single_scoredic)

    # result_json = os.path.join(root, "full_result_gemini_flash.json")
    # with open(result_json, 'r', encoding='utf-8') as f:
    #     results = json.load(f)

    domain_list = [
        "physics", "sports", "chemistry", "math", "music", "eco", "his", "geography", "biology",  "ComputerScience"
    ]
    full = [single_scoredic]

    full_count = 0
    for domain in domain_list:
        count = 0
        reasoning_score = 0
        consis_score = 0
        consis_count = 0
        read_score = 0
        hard_full_score = 0
        for r in full_results:
            r_doamin = r['task_id'].split('_')[0]
            if r_doamin ==  "board":
                r_doamin = "sports"
            elif r_doamin ==  "engineering":
                r_doamin = "physics"
            if r_doamin == domain:
                count += 1
                reasoning_score += r["reasoning"]["score"] * 100
                if r["consis"]["Final Score"] == "none":
                    pass
                else:
                    #print(r["consis"]["Final Score"])
                    consis_score += r["consis"]["Final Score"] * 50
                    consis_count +=1
                read_score += r["read"]["Final Score"] * 50
                hard_full_score += r["acc_score"]
                
        full_count += count
        reasoning_score = reasoning_score/count
        consis_score = consis_score/consis_count
        read_score = read_score/count
        single = {}
        single["domain"] = domain
        single["count"] = count
        single["consis_count"] = consis_count
        single["reasoning_score"] = round(reasoning_score, ndigits=1)
        single["consis_score"] = round(consis_score, ndigits=1)
        single["read_score"] = round(read_score, ndigits=1)
        single["relax_score"] = round(0.6 * reasoning_score + 0.3 * consis_score + 0.1 * read_score, ndigits=1)
        single["acc_score"] =round(hard_full_score * 100 / count, ndigits=1) 
        full.append(single)
    with open(os.path.join(root, "domain_score.json"), 'w', encoding='utf-8') as f:
        json.dump(full, f, indent=4, ensure_ascii=False)
        
