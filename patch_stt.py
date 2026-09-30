with open("interview_shield/stt.py", "r") as f:
    content = f.read()

close_code = """
    def close(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
"""

content = content.replace("    def close(self) -> None:\n        pass", close_code.strip('\n'))

if "def close" not in content:
    content += "\n" + close_code

with open("interview_shield/stt.py", "w") as f:
    f.write(content)
