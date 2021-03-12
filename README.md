# [https://github.com/Yonsm/ZhiModBus](https://github.com/Yonsm/ZhiModBus)

General ModBus Climate Component for HomeAssistant

通用 ModBus 空调插件，支持通用 ModBus 协议的空调（已知大金、美的等可以用），包括走网络 TCP 的。比 HA 官方做的更通用、更好。

## 1. 安装准备

把 `zhimodbus` 放入 `custom_components`；也支持在 [HACS](https://hacs.xyz/) 中添加自定义库的方式安装。

## 2. 配置方法

参见 [我的 Home Assistant 配置](https://github.com/Yonsm/.homeassistant) 中 [configuration.yaml](https://github.com/Yonsm/.homeassistant/blob/main/configuration.yaml)

```yaml
modbus:
  type: rtuovertcp
  host: 192.168.x.x
  port: 8899

climate:
  - platform: zhimodbus
    name: [餐厅空调, 客厅空调, 主卧空调, 儿童房空调]
    fan_mode: { registers: [6, 10, 14, 18] }
    fan_modes: { 自动: 0, 一档: 1, 二档: 2, 三档: 3, 四档: 4, 五档: 5 }
    hvac_mode: { registers: [5, 9, 13, 17] }
    hvac_modes: { 'off': 0, cool: 1, heat: 2, dry: 3, fan_only: 4 }
    hvac_off: { registers: [1, 2, 3, 4], register_type: coil }
    target_temperature: { registers: [4, 8, 12, 16] }
    temperature: { registers: [3, 6, 9, 12], register_type: input, scale: 0.1 }
```

```yaml
climate:
  - platform: zhimodbus
    hub: ModBus,
    name: [Daikin1, Daikin2, Daikin3, Daikin4],

    fan_modes: { auto: 0, 一级: 1, 二级: 2, 三级: 3, 四级: 4, 五级: 5},
    hvac_modes: { 'off': 0, cool: 1, heat: 2, dry: 3, fan_only: 4 },
    preset_modes: { away: 0, home: 1 },
    swing_modes: { off: 0, both: 1, vertical: 2, horizontal: 3},
    aux_heat_off_value: 0,
    aux_heat_on_value: 1,
    aux_hvac_off_value: 0,
    aux_hvac_on_value: 1,

    aux_heat: { registers: [?, ?, ?] },
    fan_mode: { registers: [?, ?, ?] },
    humidity: { registers: [?, ?, ?] },
    hvac_mode: { registers: [?, ?, ?] },
    hvac_off: { registers: [?, ?, ?] },
    preset_mode: { registers: [?, ?, ?] },
    swing_mode: { registers: [?, ?, ?] },
    target_humidity: { registers: [?, ?, ?] },
    target_temperature: { registers: [?, ?, ?] },
    temperature: { registers: [?, ?, ?] }
```

其中 `registers` 是批量配置（即多个空调），当然也可以是单个的寄存，register: ?。完整的寄存器配置格式和 [HomeAssistant ModBus Sensor](https://www.home-assistant.io/integrations/sensor.modbus/) 一致（但 `ZhiModBus` 支持了批量 `registers`）：

```
{ registers: [3, 6, 9, 12], register_type: input|holding|coil, slave:1, scale: 0.1, data_type: float|int|uint|custom, count: 1, structure: '>i'}
```

![PREVIEW1](https://github.com/Yonsm/ZhiModBus/blob/main/PREVIEW1.jpg)
![PREVIEW2](https://github.com/Yonsm/ZhiModBus/blob/main/PREVIEW2.jpg)

## 3. 需要的 ModBus RTU 模块

大金、美的、日立、海信等中央空调通用的方案，ModBus RTU 模块（价格 980 RMB，涨价到 2800 了？），再买了个“有人”牌的 485 串口转 WIFI 的模块（价格 199 RMB，墙裂推荐，一看就是认真做事的公司的产品），1180 RMB 搞定了。

网上没有现成的方案，过程中全部自己接线、调试，差点快被难度吓到放弃了——终于搞定了，简直是不可能完成的任务...

![PREVIEW3](https://github.com/Yonsm/ZhiModBus/blob/main/PREVIEW3.jpg)
![PREVIEW4](https://github.com/Yonsm/ZhiModBus/blob/main/PREVIEW4.jpg)

## 4. 参考

- [ZhiDash](https://github.com/Yonsm/ZhiDash)
- [Yonsm.NET](https://yonsm.github.io/modbus)
- [Hassbian.com](https://bbs.hassbian.com/thread-3581-1-1.html)
- [Yonsm's .homeassistant](https://github.com/Yonsm/.homeassistant)
