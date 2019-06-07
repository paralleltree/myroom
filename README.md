# myroom

## Requirements
  * smbus2
  * pigpio
  * bottle
  * Bottledaemon
  * python-daemon


## aehadump.py
空白区切りで入力されるMarkとSpaceの時間列からなるAEHAフォーマットの赤外線信号を解析します。
解析結果はフレームごとに表示されます。

### Options
|Option|Description|
|:-----|:----------|
|-t|単位周期を指定します。|
|-v|より詳細な表示に切り替えます。|

## server.py

### Environment Variables
|Name|Description|
|:---|:----------|
|PORT|サーバのポート番号|
|IR_WRITE_PIN|赤外線LEDを駆動するGPIOピン番号|

### GET /env
現在の気温、湿度、気圧をセンサから取得します。

### PUT /aircon
リクエストに基づきエアコンを操作する信号を送信します。

#### Request Body
|Name|Description|Examples|
|:---|:----------|:-------|
|work|運転を開始する場合にこのパラメータを指定します。|"1"|
|mode|運転モードを指定します。|"auto", "cool", "heat", "dry"|
|temp|設定温度を指定します。|24|
