// 作成日: 2026-11-16
// 目的: XIAO RP2040 + PN532 モジュールを「USB キーボード型の NFC 読み取り機」にする。
//       社員証（NTAG シールなど ISO 14443A）をかざすと、UID を 16 進で打ち込んで Enter を送る。
//       MeetingLog の確認端末（キーボード入力方式）にそのまま挿して使う。
//
// ボード: Raspberry Pi Pico/RP2040（Earle Philhower 版）の「Seeed XIAO RP2040」
//         USB Stack は既定の「Pico SDK」のまま（Keyboard ライブラリはボード定義に入っている）
// ライブラリ: Adafruit PN532（依存の Adafruit BusIO も一緒に入れる）
//
// 配線（PN532 モジュールのスイッチは I2C: SW1=ON, SW2=OFF）
//   PN532 VCC → XIAO 3V3 / GND → GND / SDA → D4 / SCL → D5（この 4 本だけで動く）
//   IRQ → D2 は任意。Adafruit PN532 1.3.3 は I2C の応答待ちを状態バイトの読み出しで行い、IRQ を使わない
//   （古い 1.2 系は IRQ を見ていたので、古い版を使うときはつなぐ）。RSTO はつながなくてよい
// 確認: arduino-cli で rp2040:rp2040:seeed_xiao_rp2040（rp2040 6.3.2、Adafruit PN532 1.3.3）向けにコンパイルが通る（2026-11-16）

#include <Wire.h>
#include <Keyboard.h>
#include <Adafruit_PN532.h>

// --- 配線と設定 ---
const uint8_t PIN_SDA = D4;          // XIAO RP2040 の D4 = GPIO6
const uint8_t PIN_SCL = D5;          // XIAO RP2040 の D5 = GPIO7
const uint8_t PIN_PN532_IRQ = D2;       // PN532 の IRQ（任意。つながなくても 1.3.3 では動く）
// ライブラリが RESET のピン番号も要求するため、使っていないピン（D10）を渡す。配線は不要
const uint8_t PIN_PN532_RESET = D10;

const uint16_t POLL_TIMEOUT_MS = 100;   // 1 回のカード探しの待ち時間
const uint16_t RELEASE_MS = 600;        // この時間カードが見えなければ「離した」とみなす（同じカードの連打を防ぐ）
const bool SEND_ENTER = true;           // 番号のあとに Enter を送る

Adafruit_PN532 nfc(PIN_PN532_IRQ, PIN_PN532_RESET, &Wire);

uint8_t lastUid[10];
uint8_t lastLen = 0;
uint32_t lastSeenMs = 0;


// PN532 が応答するまで待って初期化する（つながっていなくてもキーボードには何も送らない）
void startPn532() {
  while (true) {
    nfc.begin();
    uint32_t ver = nfc.getFirmwareVersion();
    if (ver) {
      Serial.printf("PN532 found: chip PN5%02X, firmware %d.%d\n",
                    (unsigned)((ver >> 24) & 0xFF), (int)((ver >> 16) & 0xFF), (int)((ver >> 8) & 0xFF));
      break;
    }
    Serial.println("PN532 not found. Check wiring and the I2C switch (SW1=ON, SW2=OFF). Retrying...");
    delay(1000);
  }
  nfc.setPassiveActivationRetries(0x01);   // カードがないとき長く待たない
  nfc.SAMConfig();                          // カードを読む普通のモードにする
}


// UID を 16 進の大文字（区切りなし）にする。NTAG は 7 バイト → 14 桁
// 0-9 と A-F だけなので、PC のキーボード配列（日本語/英語）が違っても同じ文字が入る
String uidToHex(const uint8_t *uid, uint8_t len) {
  static const char HEX_CHARS[] = "0123456789ABCDEF";
  String s;
  for (uint8_t i = 0; i < len; i++) {
    s += HEX_CHARS[uid[i] >> 4];
    s += HEX_CHARS[uid[i] & 0x0F];
  }
  return s;
}


void setup() {
  Serial.begin(115200);       // 動作確認用（Arduino IDE のシリアルモニタで見られる。キーボード入力とは別）
  Keyboard.begin();
  Wire.setSDA(PIN_SDA);
  Wire.setSCL(PIN_SCL);
  Wire.begin();
  startPn532();
  Serial.println("Ready. Tap a card.");
}


void loop() {
  uint8_t uid[10];
  uint8_t len = 0;
  bool found = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &len, POLL_TIMEOUT_MS);
  uint32_t now = millis();

  if (found && len > 0 && len <= sizeof(uid)) {
    bool same = (len == lastLen) && memcmp(uid, lastUid, len) == 0;
    bool released = (now - lastSeenMs) > RELEASE_MS;
    if (!same || released) {
      String hex = uidToHex(uid, len);
      Keyboard.print(hex);
      if (SEND_ENTER) {
        Keyboard.write(KEY_RETURN);
      }
      Serial.printf("Sent: %s (%d bytes)\n", hex.c_str(), len);
      memcpy(lastUid, uid, len);
      lastLen = len;
    }
    lastSeenMs = now;   // かざしている間は更新し続ける（離すまで再送しない）
  }
  delay(50);
}
