#                    .::::.
#                  .::::::::.
#                 :::::::::::
#              ..:::::::::::'
#           '::::::::::::'
#             .::::::::::
#        '::::::::::::::..
#             ..::::::::::::.
#           ``::::::::::::::::
#            ::::``:::::::::'        .:::.
#           ::::'   ':::::'       .::::::::.
#         .::::'      ::::     .:::::::'::::.
#        .:::'       :::::  .:::::::::' ':::::.
#       .::'        :::::.:::::::::'      ':::::.
#      .::'         ::::::::::::::'         ``::::.
#  ...:::           ::::::::::::'              ``::.
# ````':.          ':::::::::'                  ::::..
#                    '.:::::'                    ':'````..

# !/usr/bin/env/python
# encoding:utf-8
# author: usr
# 该程序运行于树莓派之内，负责的整个下位机的控制
import asyncio
import base64
import datetime
import json
import logging
import threading
import time
from multiprocessing import Process

import cv2
import requests
import websockets

# 基本参数
ws = 'ws://localhost:8081/controller/'
http = 'http://localhost:8081'
deviceId = "device_1"
t_local_max = 60  # 对于不太大的单交叉路口，绿灯时间一般不超过60s(没有联网情况下的本地绿地最长时间)
t_web_max = 60  # 车辆联网后得到的通过路口的最长绿灯时间
t_min = 15  # 路口不影响安全的最低通过时间
distance_max_camera = 33   # 摄像头角度所能看到的道路的最远处
distance_min_camera = 0     # 默认摄像头安装时最能看到的最近处为路口停车线
lanes_num = 3   # 一条道路的车道数，默认为3
car_len = 3     # 一般车的长度
jam_car_number = int(int(distance_max_camera-distance_min_camera)*lanes_num/car_len)    # 路口发生堵塞时的车数

# 设置日志基础参数
logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# 设置循环灯队列
# light_array = [0, 1, 2, 3]
light_array = [0]

# 获取摄像头的权限
light_cap_array = []
for i in light_array:
    light_cap_array.append(cv2.VideoCapture(i))
# 对摄像头进行基础设置
for cap in light_cap_array:
    # 调整采集图像大小为640*480
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

logging.info("摄像头已设置完成，随时可以使用")




def wait_thread():
    logging.info('name:{},time:{}'.format(threading.current_thread(),
                                          time.strftime("%Y-%m-%d %H:%M:%S")))
    print("定时器顺利完成任务")


# 获取cv2读取的图像转化为base64编码
def getByte(frame):
    img_mid = cv2.imencode('.jpg', frame)[1]
    img_str = str(base64.b64encode(img_mid))[2:-1]
    return img_str


# 使用摄像头的操作权限作为参数
def camera_once(cap, light_index, deviceCars):
    # ret （boolean） 表示是否有读取图片
    # frame （一帧图片数据）
    ret, frame = cap.read()

    img_str = getByte(frame)
    req = {'image': img_str, "deviceId": "device_1", "lightIndex": light_index}
    res = requests.post('http://127.0.0.1:8081/device/detection', json=req)
    deviceCars[light_index] = res.json()['cars']
    logging.info(str(cap) + "摄像头一次识别完成")
    print(res.json())


def detection_array(light_cap_array, light_array, deviceCars):
    threading_list = [threading.Thread(target=camera_once, args=(light_cap_array[light_array[i]], light_array[i], deviceCars)) for i in range(len(light_array))]

    for threading_once in threading_list:
        threading_once.start()


async def main():
    async with websockets.connect(ws+deviceId) as websocket:

        greeting = await websocket.recv()
        logging.info(deviceId+greeting)     # 输出连接是否成功

        result = {"lightNum": len(light_array)}
        await websocket.send(json.dumps(result))    # 发送启动的必要信息给服务器

        # 后续改进下方代码将作为一个完整的正常红绿灯进程启动，上方代码将增加强制使得某个分岔口交通灯强制绿灯的程序[!!!!!!!!!!!!!]
        while True:
            res = requests.get(http+"/device/controller/"+deviceId)
            state = int(res.json()[deviceId])    # 获取设备此时的状态码
            logging.info('state: '+str(state))
            count = 0   # 每一个正常的state循环的循环次数，遇到bug重新启动时会再次归零
            deviceCars = {}     # 识别到的车辆数量的本地保存
            sign = True  # 交通灯运行的两种模式，true为自动绿灯时长，false为固定周期
            count_down_time = 10  # 每个周期预留的10s最后的倒计时
            try:
                while True:
                    # 后续在两个分支中都分别需要添加确认状态码的代码[!!!!!!!!!!!!!!!!!]
                    # logging.info("start: "+str(datetime.datetime.now().timestamp()))
                    # logging.info("end: "+str(datetime.datetime.now().timestamp()))

                    if state == 1:
                        # 获取此刻执行的交通灯,并将其放入靠后位置
                        light_index = light_array[0]
                        light_array.remove(light_index)
                        light_array.append(light_index)
                        logging.info("此刻执行的路口为： "+str(light_index))

                        # 路口交通灯控制，第一次开启和后续循环需要的控制不同
                        if count == 0:
                            res = requests.get(http + "/device/maxGreenTime/" + deviceId)
                            # 联网后需要更新的数据
                            # ====================
                            t_web_max = int(res.json()[deviceId])  # 联网状态下获取网端的最长绿灯时间
                            # ====================
                            # =====树莓派串口通信代码========
                            # 开启全部路口的红灯, 并进行3秒倒计时
                            logging.info("全部路口的红灯开启")   # 更换树莓派串口代码！！！
                            logging.info("倒计时3s")      # 更换树莓派串口代码！！！
                            # ============================
                            # 设置定时器倒计时3s
                            timer = threading.Timer(3, wait_thread)
                            timer.start()
                            # detection_array 多摄像头性能还未经过测试!!!!!,测试后动态调节倒计时器时间
                            detection_array(light_cap_array, light_array, deviceCars)
                            timer.join()

                            # 根据车辆数据决定是采用方式一还是方式二运行
                            num = 0
                            for k, v in deviceCars.items():
                                print(str(k) + ' ' + str(v))
                                if v >= jam_car_number:
                                    num = num + 1
                            if num >= 2:
                                sign = False
                                logging.info("sign == False")
                            else:
                                sign = True

                        else:
                            # 非第一次进入循环，程序会有所不同
                            # 更新联网数据,应该放在别处
                            pass

                        # ============进入绿灯时间===============
                        logging.info(str(light_index) + '路口 绿灯亮起')
                        if sign:
                            # 模式一：动态绿灯时间，非固定周期
                            logging.info("进入模式一：动态绿灯时间，非固定周期")

                            max_time = int(time.time()+t_web_max-count_down_time)
                            min_time = int(time.time()+t_min-count_down_time)
                            while True:
                                if time.time() >= max_time:
                                    # 倒计时10s后退出
                                    timer = threading.Timer(10, wait_thread)
                                    timer.start()
                                    # =====树莓派串口通信代码========
                                    logging.info(str(light_index)+"路口 进入10s倒计时")
                                    timer.join()
                                    break
                                if deviceCars[light_index] <= 6 and time.time() > min_time:
                                    # 倒计时10s后退出
                                    timer = threading.Timer(10, wait_thread)
                                    timer.start()
                                    # =====树莓派串口通信代码========
                                    logging.info(str(light_index) + "路口 进入10s倒计时")
                                    timer.join()
                                    break
                                timer = threading.Timer(1, wait_thread)
                                timer.start()
                                camera_once(light_cap_array[light_index], light_index, deviceCars)
                                timer.join()

                            count = count + 1
                        else:
                            # 模式二：固定周期，动态分配各个路口的绿灯时间
                            logging.info("进入模式二：固定周期，动态分配各个路口的绿灯时间")
                            # 计算绿灯时间
                            sum_cars = 0
                            for k,v in deviceCars.items():
                                sum_cars = sum_cars + int(v)
                            # 下面的green_time都会预留出10s最后的倒计时时间
                            if sum_cars == 0:
                                green_time = t_min-count_down_time
                            elif deviceCars[light_index] == 0:
                                green_time = t_min-count_down_time
                            else:
                                green_time = int(int(deviceCars[light_index]/sum_cars)*120)
                                if green_time <= t_min:
                                    green_time = t_min-count_down_time
                            timer = threading.Timer(green_time, wait_thread)
                            timer.start()
                            # =====树莓派串口通信代码========
                            timer.join()
                            # 10s最后的倒计时时间
                            timer = threading.Timer(10, wait_thread)
                            timer.start()
                            logging.info(str(light_index) + "路口 进入10s倒计时")
                            # =====树莓派串口通信代码========
                            timer.join()
                            count = count + 1

                        # ============进入黄灯时间===============

                        # 设置黄灯定时器倒计时3s
                        timer = threading.Timer(3, wait_thread)
                        timer.start()
                        # =====树莓派串口通信代码(可以适当迁移至上一个阶段)========
                        logging.info(str(light_index) + " 路口 黄灯开启")  # 更换树莓派串口代码！！！
                        logging.info("倒计时3s")  # 更换树莓派串口代码！！！
                        # ===========================
                        # detection_array 多摄像头性能还未经过测试!!!!!,测试后动态调节倒计时器时间
                        detection_array(light_cap_array, light_array, deviceCars)
                        timer.join()
                        logging.info("倒计时结束后，下一个路口开绿灯，其他继续红灯")
                        # 根据车辆数据决定是采用方式一还是方式二运行
                        num = 0
                        for k, v in deviceCars.items():
                            print(str(k) + ' ' + str(v))
                            if v >= jam_car_number:
                                num = num + 1
                        if num >= 2:
                            sign = False
                            logging.info("sign == False")
                        else:
                            sign = True

                    elif state == 0 or state == 2:
                        # 该分支为程序自主运行分支
                        # 获取此刻执行的交通灯
                        light_index = light_array[0]
                        light_array.remove(light_index)
                        light_array.append(light_index)

                        logging.info("此刻执行的路口为： " + str(light_index))

                        logging.info("state == 0 | state == 2")
                        time.sleep(2)

                    else:
                        # state没有参数才会进行到这一步，说明联网失败了，自动切换到自主运行，等待服务器端修复
                        state = 0
                        # 编写日志，后续通过守护线程将日志发送到服务器
                        logging.error("[ERROR]联网失败")

            except Exception:
                requests.post(http+"/device/controller/"+deviceId+"/"+str(0))
                result = {"warm": "[最高等级故障]设备运行崩溃，切换到自动运行"}
                await websocket.send(json.dumps(result))
                logging.info("[WARM 最高等级故障]设备运行崩溃，切换到自动运行")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    # task = [asyncio.ensure_future(main(i)) for i in range(5)]
    # tasks = asyncio.wait(task)
    # loop.run_until_complete(tasks)
    loop.run_until_complete(main())
    loop.close()