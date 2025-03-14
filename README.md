# net_learning
## About me
- ✨ 系級：科技系4年級
- ✨ 姓名：簡珮軒
- ✨ 113-2 網路輔助學習系統研究 **Learning record and homework submission**
## Record
### 2025/02/17
- Create VS Code Virtual Environment
  ```
  python3 -m venv venv
  ```
  ```
  source venv/bin/activate
  ```
- Use Python to use Hugging Face Pipeline
  ```
  pip install torch torchvision torchaudio
  ```
  ![result](https://github.com/cpeggy/net_learnin/blob/main/%E6%88%AA%E5%9C%96%202025-02-17%2023.54.46.png)
### 2025/02/24
- Use Gemini API KEY as AI agent
  ```
  UserMessage(content="What is AI?")
  ```
  - Response
  ![result](https://github.com/cpeggy/net_learnin/blob/main/%E6%88%AA%E5%9C%96%202025-02-24%2014.48.32.png)
  - Full code: [Here](https://github.com/cpeggy/net_learnin/blob/main/week2rec/test_aimodel.py)
- multiAgent
  - Three agents: assistant, web_surfer, critic
  - Stop with **textMentionTermination("TERMINATE")**
  - Full code: [Here](https://github.com/cpeggy/net_learnin/blob/main/week2rec/test_aiage3.py)
- AI Agent service diagram
  - Function：To create a AI Agent to make persona by analying survey result and other resource.
  - Diagram：
  - ![dia](https://github.com/cpeggy/net_learnin/blob/main/%E6%88%AA%E5%9C%96%202025-03-03%2009.23.06.png)
### 2025/03/03 
- Data agent
  - Full code (for practice): [Here](https://github.com/cpeggy/net_learnin/blob/main/week3rec/test_dataagent.py)
    - Based on the authorization of data from my company, data and result can't shared.
  - Diagram：
  - ![dia](https://github.com/cpeggy/net_learnin/blob/main/%E6%88%AA%E5%9C%96%202025-03-03%2023.42.51.png)
  - Next:
    - customize assistants property
    - to authorize old data
### 2025/03/10
- Project version of Data agent
  - full code: [Here](https://github.com/cpeggy/net_learnin/blob/main/week3rec/proj_dataagent.py)
- Active with UI
  - full code: [Here](https://github.com/cpeggy/net_learnin/blob/main/week4rec/proj_dataagentUI.py)
  - Based on the authorization of data from my company, data and result can't shared.

## Homework
- [HW1](https://github.com/cpeggy/net_learnin/blob/main/week2rec/test_aiage3.py)
- [HW2](https://github.com/cpeggy/net_learnin/blob/main/week4rec/proj_dataagentUI.py)
## Course ppt
- [Week 1](https://docs.google.com/presentation/d/1ao4jEB4lJg-ldtN8t88yivU4lr_uZpf-NxSrNZF9O7I/edit#slide=id.p)
