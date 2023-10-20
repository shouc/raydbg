# RayDBG

A tool for static and dynamic analysis of Ray programs, using LLM. 

## Installation
```bash
pip3 install raydbg

# Setup CodeQL (optional)
raydbg init
```


## Usage

Make sure you have set `OPENAI_KEY` environment variable to your OpenAI API key if you want to use LLM for more accurate analysis. 
You can also use `--no-llm` to disable LLM feature.

Static Analysis:
```bash
raydbg static --target <path_to_ray_file>
```


Dynamic Analysis:
```bash
raydbg dynamic --target <path_to_ray_file>
```


## Example

```bash
git clone https://github.com/shouc/raydbg.git
cd raydbg
```


Run static analysis:
```bash
raydbg static --target examples/pi.py
```


Run dynamic analysis:
```bash
raydbg dynamic --target examples/pi.py
```
