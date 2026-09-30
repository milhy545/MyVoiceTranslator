import re
with open("interview_shield/stt.py", "r") as f:
    content = f.read()

close_code = """    def close(self) -> None:
        if getattr(self, "model", None) is not None:
            del self.model
            self.model = None
            
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass"""

content = re.sub(r'    def close\(self\) -> None:.*?        except ImportError:\n            pass', close_code, content, flags=re.DOTALL)

with open("interview_shield/stt.py", "w") as f:
    f.write(content)
