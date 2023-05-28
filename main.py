import asyncio
import os
import pytesseract
from tkinter import *
import pyautogui
import mouse
import keyboard
import cv2
from PIL import Image

import numpy as np

from typing import List, Tuple

import requests
import json

from types import SimpleNamespace

#tesseract OCR
pytesseract.pytesseract.tesseract_cmd = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

class Config(SimpleNamespace):
    def __init__(self, lang, url, id, secret, source, target):
        super().__init__(
            lang = lang, 
            vert = lang in "vert",
            url = url, 
            id = id,
            secret = secret,
            source = source,
            target = target
        )

class GUI(Tk):
    def __init__(self, config):
        self.config = config

        self.toplevel, self.canvas = None, None

        self.text = Text()
        self.text.pack(fill="both", expand=True)

        self.path = os.path.join(".", "snapshot")

        self.history: List[Tuple[int]] = []
        self.capacity = 10

        self.repeat = False

        #self.wm_attributes("-topmost", 1)

    def __build_canvas(self) -> Tuple[Toplevel, Canvas]:
        toplevel = Toplevel()

        # clear canvas
        canvas = Canvas(toplevel, highlightthickness=0, bd=0, relief="ridge", bg="white")
        canvas.master.wm_attributes("-transparentcolor", "white")
        canvas.pack(fill="both", expand=True)
        toplevel.update()

        # clear toplevel
        toplevel.attributes("-fullscreen", True)
        toplevel.wm_attributes("-topmost", True)
        toplevel.focus_force()
        toplevel.overrideredirect(True)
        toplevel.update()

        return toplevel, canvas
    
    def __save_snapshot(self, name, region: Tuple[int]) -> Image:
        path = os.path.join(self.path, name)
        return pyautogui.screenshot(path, region=region)

    def __add_history(self, region: Tuple[int]) -> None:
        self.history = self.history[1:self.capacity] + [region]

    async def __get_area(self) -> Tuple[int]:
        if not self.toplevel and not self.canvas:
            self.toplevel, self.canvas = self.__build_canvas()

        start_pos = pyautogui.position()

        region = (0, 0, 0, 0)
        loop = True

        while loop:
            current_pos = pyautogui.position()
            self.canvas.create_rectangle(
                start_pos.x, start_pos.y, 
                current_pos.x, current_pos.y, 
                outline="red", 
                tags="rect", 
                width=2
            )
            
            if mouse.is_pressed("left"):
                end_pos = pyautogui.position()
                x1, y1 = start_pos.x, start_pos.y
                x2, y2 = end_pos.x,   end_pos.y
                x, y   = abs(x2-x1), abs(y2-y1)
                region = (min(x1,x2)+1,min(y1,y2)+1,x-2,y-2)
                loop = False
            
            self.canvas.update()
            await asyncio.sleep(0.01)
            self.canvas.delete("rect")
            self.toplevel.update()

        return region
            

    async def textualization(self, image: Image) -> str:
        image = np.array(image)
        target = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        target = cv2.threshold(target, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        result = pytesseract.image_to_string(target, lang=self.config.lang)[:-1].strip()

        if self.config.vert:
            result = "".join([word for word in result if word not in [' ', '\n']])

        return result

    async def snapshot(self):
        if not self.toplevel and not self.canvas:
            self.toplevel, self.canvas = self.__build_canvas()

        region = await self.__get_area() 

        image = self.__save_snapshot(
            name="snapshot.png",
            region=region
        )

        self.__add_history(region)
        result = await self.textualization(image)

        self.text.delete("1.0", END)
        self.text.insert(END, result)

    async def snapshot_same_area(self):
        if not self.history:
            return
        
        image = self.__save_snapshot(
            name="snapshot.png",
            region=self.history[-1]
        )
        result = await self.textualization(image)

        self.text.delete("1.0", END)
        self.text.insert(END, result)

    async def snapshot_repeat(self):
        if not self.history:
            return
        
        self.repeat ^= True
        await self.__snapshot_repeat()
    
    async def __snapshot_repeat(self):
        current_text = ""
        while self.repeat:
            
            image = self.__save_snapshot(
                name="snapshot.png",
                region=self.history[-1]
            )

            result = await self.textualization(image)
            
            if result != current_text:
                current_text = result
                self.text.delete("1.0", END)
                self.text.insert(END, current_text)

            await asyncio.sleep(1)

    async def translate(self):
        target = self.text.get("1.0", END)

        print(self.config)
        result = requests.post(self.config.url,
            headers= {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Naver-Client-Id": self.config.id,
                "X-Naver-Client-Secret": self.config.secret
            },
            data={
                "source": self.config.source,
                "target": self.config.target,
                "text": f"{target}"
            }
        )

        print(result)

        self.text.delete("1.0", END)
        content = result.content.decode(encoding="utf-8")
        content = json.loads(content)["message"]["result"]["translatedText"]
        self.text.insert(END, f"{target}\n------\n\n{content}")

    async def run(self):
        mainloop()

async def main():
    config = Config(
        lang = "jpn+jpn_vert", # ocr_lang = 'kor+eng', 'eng', 'jpn+jpn_vert'
        url = "https://openapi.naver.com/v1/papago/n2mt", 
        id = os.getenv("NAVERID"),
        secret = os.getenv("NAVERSECRET"),
        source="ja",
        target="ko"
    )
    print(os.getenv("NAVERID"))
    
    gui = GUI(config=config)

    keyboard.add_hotkey("ctrl+q", lambda : asyncio.run(gui.snapshot()))
    keyboard.add_hotkey("ctrl+r", lambda : asyncio.run(gui.snapshot_repeat()))
    keyboard.add_hotkey("ctrl+t", lambda : asyncio.run(gui.translate()))
    await gui.run()
    return

if __name__ == "__main__":
    asyncio.run(main())