"""把回合接到本产品的提交路径上（语音、主动开口）。

agent 层只定义 BrainPort 与实现；「把一条输入交给 SubmitService、再读回事件流」是
这个产品的往里接法，所以放在 service。
"""
