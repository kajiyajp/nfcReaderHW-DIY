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
//   VCC は 5V でも動くが、先に SDA・SCL の電圧を測る（3.6V 以下ならよい。くわしくは firmware/README.md）
//   IRQ → D2 は任意。Adafruit PN532 1.3.3 は I2C の応答待ちを状態バイトの読み出しで行い、IRQ を使わない
//   （古い 1.2 系は IRQ を見ていたので、古い版を使うときはつなぐ）。RSTO はつながなくてよい
//   ブザー（任意。アクティブブザー＝電圧をかけると決まった高さで鳴るもの）は NPN トランジスタで鳴らす:
//     D3 → 1kΩ → NPN のベース、エミッタ → GND、コレクタ → ブザーの −、ブザーの ＋ → 5V（くわしくは firmware/README.md）
// 確認: arduino-cli で rp2040:rp2040:seeed_xiao_rp2040（rp2040 6.3.2、Adafruit PN532 1.3.3）向けにコンパイルが通る（2026-11-16）
//       実機（XIAO RP2040 + PN532 モジュール V3、VCC は 3V3 と 5V の両方）で NTAG215 の社員証を読めた（2026-11-19）

#include <Wire.h>
#include <EEPROM.h>
#include <Keyboard.h>
#include <Adafruit_PN532.h>
#include <hardware/pio.h>
#include <hardware/clocks.h>
#include <pico/time.h>

// --- 配線と設定 ---
const uint8_t PIN_SDA = D4;          // XIAO RP2040 の D4 = GPIO6
const uint8_t PIN_SCL = D5;          // XIAO RP2040 の D5 = GPIO7
const uint8_t PIN_PN532_IRQ = D2;       // PN532 の IRQ（任意。つながなくても 1.3.3 では動く）
// ライブラリが RESET のピン番号も要求するため、使っていないピン（D10）を渡す。配線は不要
const uint8_t PIN_PN532_RESET = D10;
const uint8_t PIN_BUZZER = D3;          // ブザーを鳴らす NPN トランジスタのベース（HIGH で鳴る）
const bool USE_BUZZER = true;           // false にすると音を出さない（LED だけ）

// 1 回のカード探しの待ち時間の上限。探す回数を 1 回に絞っているので、カードがなければ PN532 がすぐ「なし」と返す。
// 上限を短くしすぎると、PN532 が探している途中で次の命令を送ることになるので、余裕をもたせる
const uint16_t POLL_TIMEOUT_MS = 1000;
const uint32_t I2C_TIMEOUT_MS = 200;    // I2C の 1 回の通信の上限（固まっても止まり続けない）
// この時間カードが見えなければ「離した」とみなす（同じカードの連打を防ぐ）。
// 離す途中で 0.3〜0.7 秒読めないことがあり、600ms だと 30 回に 1 回、番号が 2 回入った（2026-11-19 の実機確認）ので余裕をもたせる。
// 同じカードをもう一度入力したいときは、1.5 秒以上離してからかざす
const uint16_t RELEASE_MS = 1500;
const bool SEND_ENTER = true;           // 番号のあとに Enter を送る

Adafruit_PN532 nfc(PIN_PN532_IRQ, PIN_PN532_RESET, &Wire);

uint8_t lastUid[10];
uint8_t lastLen = 0;
uint32_t lastSeenMs = 0;

// かざした人への反応の種類（意味は、下の「かざした人への反応」の説明を読む）
enum Feedback { FB_SENT, FB_REPEAT, FB_ERROR, FB_OK };

// 音の鳴らし方（意味は、下の「ブザー」の説明を読む）。「鳴らす時間, 止める時間, 鳴らす時間, …」を ms で並べ、0 で終わる
const uint16_t BEEP_SENT[] = {300, 0};                         // ピッ 0.3 秒
const uint16_t BEEP_ERROR[] = {100, 100, 100, 100, 100, 0};    // ピピピ 0.1 秒×3
const uint16_t BEEP_READY[] = {50, 50, 50, 0};                 // ピピ 0.05 秒×2


// ---------------------------------------------------------------- 場所の番号（どの読み取り機でかざしたか）
// 読み取り機ごとに 1〜4 桁の数字を XIAO のフラッシュに保存する（電源を切っても、スケッチを書き直しても残る）。
// 設定してあると、番号の前に「L 場所 U」を付けて打ち込む（例: 場所 12 → L12U04A1B2C3D4E5F6）。未設定なら UID だけ。
// 区切りに英大文字を使うのは、記号だとキーボードの配列や日本語入力で別の文字に変わるため。
// 設定はシリアルモニタ（115200bps、改行あり）から:
//   LOC 12   … 場所を 12 にする      LOC OFF … 場所をなしにする      LOC … いまの設定を表示する
const uint32_t CONFIG_MAGIC = 0x4E464331;   // 保存した設定の目印（"NFC1"）
const uint8_t LOCATION_MAX_DIGITS = 4;
struct Config {
  uint32_t magic;
  char location[LOCATION_MAX_DIGITS + 1];   // 数字の文字列。空ならなし（"012" と "12" は別の番号として扱う）
};
Config config;


void loadConfig() {
  EEPROM.begin(256);
  EEPROM.get(0, config);
  bool ok = (config.magic == CONFIG_MAGIC) && (strnlen(config.location, sizeof(config.location)) <= LOCATION_MAX_DIGITS);
  for (uint8_t i = 0; ok && config.location[i]; i++) {
    ok = isDigit(config.location[i]);
  }
  if (!ok) {   // まだ保存していない、または壊れている → 場所なしで始める
    config.magic = CONFIG_MAGIC;
    config.location[0] = '\0';
  }
}


void printLocation() {
  if (config.location[0]) {
    Serial.printf("Location code: %s (sends L%sU<card number>)\n", config.location, config.location);
  } else {
    Serial.println("Location code: not set (sends the card number only). Set with: LOC 12");
  }
}


// シリアルから来た 1 行を処理する（LOC の設定だけ）
void handleCommand(String line) {
  line.trim();
  line.toUpperCase();
  if (line.length() == 0) {
    return;
  }
  if (!line.startsWith("LOC")) {
    Serial.println("Unknown command. Use: LOC 12 (set) / LOC OFF (clear) / LOC (show)");
    return;
  }
  String arg = line.substring(3);
  arg.replace("=", " ");
  arg.trim();
  if (arg.length() == 0) {
    printLocation();
    return;
  }
  if (arg != "OFF") {
    bool digits = arg.length() <= LOCATION_MAX_DIGITS;
    for (uint16_t i = 0; digits && i < arg.length(); i++) {
      digits = isDigit(arg[i]);
    }
    if (!digits) {
      Serial.printf("Location code must be 1 to %d digits (or OFF). Nothing changed.\n", LOCATION_MAX_DIGITS);
      return;
    }
  }
  memset(config.location, 0, sizeof(config.location));
  if (arg != "OFF") {
    arg.toCharArray(config.location, sizeof(config.location));
  }
  EEPROM.put(0, config);
  bool saved = EEPROM.commit();
  Serial.println(saved ? "Saved." : "SAVE FAILED (the setting is kept only until power off).");
  if (saved) {
    beep(BEEP_READY);   // 保存できたことを音でも知らせる
  }
  printLocation();
}


// シリアルに届いた文字を、改行までためて処理する（loop から毎回呼ぶ。待たない）
void pollSerialCommands() {
  static String buf;
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') {
      handleCommand(buf);
      buf = "";
    } else if (buf.length() < 32) {
      buf += ch;
    }
  }
}


// ---------------------------------------------------------------- かざした人への反応（基板上の RGB LED）
// XIAO RP2040 の RGB LED（WS2812。データ GPIO12、電源 GPIO11）を、RP2040 の PIO で直接動かす（追加のライブラリは要らない）。
// 読み取り機は PC から返事を受け取らないので、示せるのは読み取り機が自分で分かることだけ
// （社員証が登録済みかどうかは、確認端末の画面に出る）:
//   待機          … 青をごく弱く点灯（電源が入っていて、PN532 も動いている）
//   FB_SENT      … 緑 1 秒（読めて、番号を送った）
//   FB_REPEAT    … 黄（同じカードをまた読んだが、送らなかった。置いたままの間・離して 1.5 秒以内のかざし直し）
//   FB_ERROR     … 赤 0.2 秒の点滅（PN532 が見つからない・応答しない。FB_OK が来るまで続く）
// 音（ブザー）は、下の「ブザー」のところで鳴らし方を決めている
// （enum Feedback は、最初の関数より前に要るので、ファイルの上のほうで定義している）

const uint32_t LED_SENT_MS = 1000;     // 緑の時間
const uint32_t LED_REPEAT_MS = 500;    // 黄の時間（置いている間は約 0.2 秒ごとに読めるので、点きっぱなしに見える）
const uint32_t LED_BLINK_MS = 200;     // 赤の点滅の間隔
// 色は 0xRRGGBB。まぶしくないよう暗めにしている
const uint32_t COLOR_OFF = 0x000000, COLOR_IDLE = 0x000004, COLOR_SENT = 0x003000,
               COLOR_REPEAT = 0x281800, COLOR_ERROR = 0x300000;

volatile bool ledError = false;
volatile uint32_t ledSentUntil = 0, ledRepeatUntil = 0;
PIO ledPio = pio0;
uint ledSm = 0;
repeating_timer_t ledTimer;

// WS2812 の信号を出す PIO のプログラム（pico-examples の ws2812.pio と同じ 4 命令。1 ビット = 10 クロック）
const uint16_t WS2812_INSTRUCTIONS[] = {0x6221, 0x1123, 0x1400, 0xa442};


void ledWrite(uint32_t rgb) {
  // WS2812 は 緑・赤・青 の順に、上の桁から送る
  uint32_t grb = ((rgb & 0x00FF00) << 8) | ((rgb & 0xFF0000) >> 8) | (rgb & 0x0000FF);
  pio_sm_put(ledPio, ledSm, grb << 8);
}


// 50ms ごとにタイマーから呼ばれ、いまの状態の色を出す（カードを探している間や、打ち込み中も止まらない）
bool ledTick(repeating_timer_t *) {
  static uint32_t shown = 0xFFFFFFFF;
  uint32_t now = millis();
  uint32_t color = COLOR_IDLE;
  if (ledError) {
    color = ((now / LED_BLINK_MS) % 2) ? COLOR_ERROR : COLOR_OFF;
  } else if ((int32_t)(ledSentUntil - now) > 0) {
    color = COLOR_SENT;
  } else if ((int32_t)(ledRepeatUntil - now) > 0) {
    color = COLOR_REPEAT;
  }
  if (color != shown) {
    ledWrite(color);
    shown = color;
  }
  return true;
}


void ledBegin() {
  pinMode(NEOPIXEL_POWER, OUTPUT);
  digitalWrite(NEOPIXEL_POWER, HIGH);
  pio_program_t program = {};
  program.instructions = WS2812_INSTRUCTIONS;
  program.length = 4;
  program.origin = -1;
  uint offset = pio_add_program(ledPio, &program);
  ledSm = pio_claim_unused_sm(ledPio, true);
  pio_gpio_init(ledPio, PIN_NEOPIXEL);
  pio_sm_set_consecutive_pindirs(ledPio, ledSm, PIN_NEOPIXEL, 1, true);
  pio_sm_config c = pio_get_default_sm_config();
  sm_config_set_wrap(&c, offset, offset + 3);
  sm_config_set_sideset(&c, 1, false, false);
  sm_config_set_sideset_pins(&c, PIN_NEOPIXEL);
  sm_config_set_out_shift(&c, false, true, 24);
  sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_TX);
  sm_config_set_clkdiv(&c, clock_get_hz(clk_sys) / (800000.0f * 10));
  pio_sm_init(ledPio, ledSm, offset, &c);
  pio_sm_set_enabled(ledPio, ledSm, true);
  add_repeating_timer_ms(50, ledTick, nullptr, &ledTimer);
}


// ---------------------------------------------------------------- ブザー（音）
// アクティブブザーなので、音の高さは選べない（ブザーで決まっている）。長さと回数で区別する:
//   BEEP_SENT  … ピッ 0.3 秒（読めて、番号を送った。LED の緑と同時）
//   BEEP_ERROR … ピピピ 0.1 秒×3（PN532 が見つからない・応答しなくなったときに 1 回だけ。直るまで LED の赤の点滅で示す）
//   BEEP_READY … ピピ 0.05 秒×2（起動して使えるようになった。LOC の保存に成功した）
//   同じカードを読んで送らなかったとき（LED の黄）は鳴らさない（置いたままだと 0.2 秒ごとに起きてうるさいため）
// 鳴らし方（BEEP_SENT など）は、LOC の設定の処理でも使うので、ファイルの上のほうで定義している
const uint32_t BEEP_TICK_MS = 10;          // 鳴らし方を進める間隔（短い音 0.05 秒を刻めるように）

const uint16_t *volatile beepRequest = nullptr;   // 次に鳴らす音（loop から入れ、タイマーが受け取る）
repeating_timer_t beepTimer;


// 10ms ごとにタイマーから呼ばれ、鳴らし方の表を 1 段ずつ進める（カードを探している間や、打ち込み中も止まらない）
bool beepTick(repeating_timer_t *) {
  static const uint16_t *pattern = nullptr;
  static uint8_t step = 0;
  static uint32_t left = 0;     // いまの段の残り時間（ms）
  const uint16_t *req = beepRequest;
  if (req) {                    // 新しい音が来たら、鳴っている途中でも最初から鳴らし直す
    beepRequest = nullptr;
    pattern = req;
    step = 0;
    left = pattern[0];
  }
  if (!pattern) {
    return true;
  }
  if (left == 0) {              // この段が終わった → 次の段へ（0 なら鳴らし終わり）
    step++;
    left = pattern[step];
    if (left == 0) {
      pattern = nullptr;
      digitalWrite(PIN_BUZZER, LOW);
      return true;
    }
  }
  digitalWrite(PIN_BUZZER, (step % 2 == 0) ? HIGH : LOW);   // 偶数の段は鳴らす、奇数の段は止める
  left = (left > BEEP_TICK_MS) ? left - BEEP_TICK_MS : 0;
  return true;
}


void beepBegin() {
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  add_repeating_timer_ms(BEEP_TICK_MS, beepTick, nullptr, &beepTimer);
}


// 音を鳴らす（待たない。鳴らすのはタイマーが行う）
void beep(const uint16_t *pattern) {
  if (USE_BUZZER) {
    beepRequest = pattern;
  }
}


// かざした人への反応を出す（LED と音）
void feedback(Feedback f) {
  uint32_t now = millis();
  switch (f) {
    case FB_SENT:
      ledSentUntil = now + LED_SENT_MS;
      beep(BEEP_SENT);
      break;
    case FB_REPEAT:
      ledRepeatUntil = now + LED_REPEAT_MS;   // 音は鳴らさない
      break;
    case FB_ERROR:
      if (!ledError) {   // 異常になったときだけ鳴らす（直るまで何度も呼ばれるため）
        beep(BEEP_ERROR);
      }
      ledError = true;
      break;
    case FB_OK:
      ledError = false;
      break;
  }
}


// カードを探す回数の上限を設定する（RFConfiguration の MaxRetries）
// ライブラリの setPassiveActivationRetries() は PN532 の返事を読まずに終わるため、I2C では返事が PN532 に残り、
// 次の命令から通信がかみ合わなくなる（2026-11-19 の実機確認で、この直後から PN532 が応答しなくなった）。
// ここでは同じ命令を送ったあと、返事（RDY 1 バイト＋応答フレーム 9 バイト）を読み捨てる
bool setPassiveActivationRetries(uint8_t maxRetries) {
  uint8_t cmd[] = {PN532_COMMAND_RFCONFIGURATION, 5, 0xFF, 0x01, maxRetries};
  return sendRfConfiguration(cmd, sizeof(cmd));
}


// 電波を止める（RFConfiguration の RF field を off）。次にカードを探すとき、PN532 が自動で電波を出し直す。
// 探すたびに電波を切って、カードを最初の状態に戻す（下の setRxGain の測定は、この手順で行った）
bool rfFieldOff() {
  uint8_t cmd[] = {PN532_COMMAND_RFCONFIGURATION, 1, 0x00};
  return sendRfConfiguration(cmd, sizeof(cmd));
}


// 受信の感度を切り替える（RFConfiguration の項目 0x0A。106kbps Type A のアナログ設定 11 バイトのうち、先頭の RFCfg だけ変える）
// カードをアンテナにぴったり置くと、標準の感度（38dB）ではカードの返事を受け取れず、置いている間ずっと読めない。
// そのため「離した」と誤って判定し、離すときにもう一度読めて番号が 2 回入った（2026-11-19 の実機確認）。
// 感度を下げる（18〜33dB）と、ぴったり置いても 10 回中 10 回読めた。離れたカードは標準の感度で読むので、
// 探すたびに「標準」と「低い」を交互に使い、近くても遠くても 2 回に 1 回は読めるようにする
const uint8_t RFCFG_FAR = 0x59;    // 標準（受信 38dB）。離れたカード用
const uint8_t RFCFG_NEAR = 0x19;   // 受信 23dB。アンテナにぴったり置いたカード用
bool setRxGain(uint8_t rfcfg) {
  // 残りの 10 バイトは PN532 の標準値（GsNOn, CWGsP, ModGsP, DemodWhenRfOn, RxThreshold, DemodWhenRfOff, GsNOff, ModWidth, MifNFC, TxBitPhase）
  uint8_t cmd[] = {PN532_COMMAND_RFCONFIGURATION, 0x0A,
                   rfcfg, 0xF4, 0x3F, 0x11, 0x4D, 0x85, 0x61, 0x6F, 0x26, 0x62, 0x87};
  return sendRfConfiguration(cmd, sizeof(cmd));
}


// RFConfiguration の命令を送り、返事（RDY 1 バイト＋応答フレーム 9 バイト）を読み捨てる
bool sendRfConfiguration(uint8_t *cmd, uint8_t len) {
  if (!nfc.sendCommandCheckAck(cmd, len)) {
    return false;
  }
  Wire.requestFrom((uint8_t)PN532_I2C_ADDRESS, (uint8_t)10);
  while (Wire.available()) {
    Wire.read();
  }
  return true;
}


// I2C の線を解放させてから、I2C を始め直す。線の状態（始め直す前に読んだ値）を sda・scl に返す。
// XIAO だけが再起動すると（書き込み直後など）、PN532 が通信の途中で止まり、線を押さえたままになることがある。
// SCL を 16 回動かして PN532 に残りのビットを出し切らせ、最後に STOP（SCL が 1 の間に SDA を 0→1）を送る
void recoverI2cBus(int *sda, int *scl) {
  Wire.end();
  pinMode(PIN_SDA, INPUT_PULLUP);
  pinMode(PIN_SCL, INPUT_PULLUP);
  delay(2);
  *sda = digitalRead(PIN_SDA);
  *scl = digitalRead(PIN_SCL);
  for (int i = 0; i < 16; i++) {
    pinMode(PIN_SCL, OUTPUT);
    digitalWrite(PIN_SCL, LOW);
    delayMicroseconds(10);
    pinMode(PIN_SCL, INPUT_PULLUP);
    delayMicroseconds(10);
  }
  pinMode(PIN_SDA, OUTPUT);
  digitalWrite(PIN_SDA, LOW);
  delayMicroseconds(10);
  pinMode(PIN_SDA, INPUT_PULLUP);
  delay(2);
  Wire.setSDA(PIN_SDA);
  Wire.setSCL(PIN_SCL);
  Wire.setTimeout(I2C_TIMEOUT_MS, true);
  Wire.begin();
}


// PN532 が応答するまで待って初期化する（つながっていなくてもキーボードには何も送らない）
void startPn532() {
  while (true) {
    nfc.begin();
    uint32_t ver = nfc.getFirmwareVersion();
    if (ver) {
      Serial.printf("PN532 found: chip PN5%02X, firmware %d.%d\n",
                    (unsigned)((ver >> 24) & 0xFF), (int)((ver >> 16) & 0xFF), (int)((ver >> 8) & 0xFF));
      feedback(FB_OK);
      break;
    }
    feedback(FB_ERROR);
    int sda = 0, scl = 0;
    recoverI2cBus(&sda, &scl);
    // SDA・SCL は、I2C を止めて線を読んだ値（1 が正常。0 なら、その線がどこかで 0V に押さえられている）
    Serial.printf("PN532 not found (SDA=%d SCL=%d). Check wiring and the I2C switch (SW1=ON, SW2=OFF). Retrying...\n",
                  sda, scl);
    delay(1000);
  }
  nfc.SAMConfig();                          // カードを読む普通のモードにする
  setPassiveActivationRetries(0x01);        // カードがないとき長く待たない
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
  // シリアルモニタが開くのを最大 3 秒待つ（起動直後の表示を見落とさないため。開かなくても先へ進む）
  while (!Serial && millis() < 3000) {
    delay(10);
  }
  loadConfig();
  printLocation();
  Keyboard.begin();
  ledBegin();
  beepBegin();
  Wire.setSDA(PIN_SDA);
  Wire.setSCL(PIN_SCL);
  Wire.setTimeout(I2C_TIMEOUT_MS, true);   // 時間切れのときは I2C をやり直す
  Wire.begin();
  startPn532();
  beep(BEEP_READY);   // 使えるようになったことを音で知らせる
  Serial.println("Ready. Tap a card.");
}


void loop() {
  uint8_t uid[10];
  uint8_t len = 0;
  static bool nearGain = false;   // 受信の感度を 1 回ごとに切り替える（遠いカード用 ⇔ 近いカード用）
  static uint16_t polls = 0, hits = 0;   // 5 秒ごとの表示用（探した回数と読めた回数）
  nearGain = !nearGain;
  setRxGain(nearGain ? RFCFG_NEAR : RFCFG_FAR);
  bool found = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &len, POLL_TIMEOUT_MS);
  uint32_t now = millis();
  polls++;
  if (found) {
    hits++;
  }

  static uint16_t misses = 0;   // 前に読めてから、続けて読めなかった回数（表示用）
  if (found && len > 0 && len <= sizeof(uid)) {
    bool same = (len == lastLen) && memcmp(uid, lastUid, len) == 0;
    uint32_t gap = now - lastSeenMs;   // 前に読めてからの時間
    bool released = gap > RELEASE_MS;
    if (!same || released) {
      String hex = uidToHex(uid, len);
      if (config.location[0]) {   // 場所の番号があれば前に付ける（例: L12U04A1B2C3D4E5F6）
        hex = String("L") + config.location + "U" + hex;
      }
      feedback(FB_SENT);
      Keyboard.print(hex);
      if (SEND_ENTER) {
        Keyboard.write(KEY_RETURN);
      }
      // 同じカードの再送のときは、読めなかった時間と回数も出す（重複して入るときの調整用）
      Serial.printf("Sent: %s (%d bytes)%s gap=%lums misses=%u\n", hex.c_str(), len,
                    same ? " SAME CARD" : "", (unsigned long)gap, misses);
      memcpy(lastUid, uid, len);
      lastLen = len;
    } else {
      feedback(FB_REPEAT);   // 同じカードをまた読んだ（送らない）
      if (gap > 250) {
        // かざしている途中で読めない時間があった（再送はしていない）
        Serial.printf("  held: gap=%lums misses=%u\n", (unsigned long)gap, misses);
      }
    }
    misses = 0;
    lastSeenMs = millis();   // かざしている間は更新し続ける（離すまで再送しない）。打ち込みにかかった時間は数えない
  } else if (misses < 0xFFFF) {
    misses++;
  }
  // 5 秒ごとに動いていることを表示する（PN532 が応答しているかも見る。シリアルモニタで動作を確かめる用）
  static uint32_t lastBeatMs = 0;
  if (now - lastBeatMs >= 5000) {
    lastBeatMs = now;
    uint32_t ver = nfc.getFirmwareVersion();
    feedback(ver ? FB_OK : FB_ERROR);
    // reads は、この 5 秒で「読めた回数/探した回数」。カードを置いたままなら半分以上になる
    Serial.printf("Waiting for a card... PN532 %s reads=%u/%u\n", ver ? "OK" : "NOT RESPONDING", hits, polls);
    polls = 0;
    hits = 0;
  }
  rfFieldOff();   // 次に探すまで電波を止めて、カードを最初の状態に戻す
  pollSerialCommands();
  delay(50);
}
