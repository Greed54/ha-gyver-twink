/*
  Скетч к проекту "GyverTwink"
  - Страница проекта (схемы, описания): https://alexgyver.ru/gyvertwink/
  - Исходники на GitHub: https://github.com/AlexGyver/GyverTwink
  Проблемы с загрузкой? Читай гайд для новичков: https://alexgyver.ru/arduino-first/
  AlexGyver, AlexGyver Technologies, 2021
*/

/*
  1.1 - исправлена калибровка больше 255 светодиодов
  1.2 - исправлена ошибка с калибровкой
  1.3 - (ha-gyver-twink) расширенный UDP протокол для Home Assistant:
        текущий эффект, постоянный выбор эффекта, параметры эффекта без
        принудительного показа, push-уведомления подписчику, OTA, mDNS.
        Старые команды и форматы ответов не изменены - приложение GyverTwink работает как раньше.
        Описание протокола: docs/protocol.md
*/

/*
  Мигает синим - открыт портал
  Мигает жёлтым - подключаемся к точке
  Мигнул зелёным - подключился к точке
  Мигнул красным - ошибка подключения к точке
  Мигнул розовым - создал точку
*/

// ================ НАСТРОЙКИ ================
#define BTN_PIN D3      // пин кнопки
#define BTN_TOUCH 0     // 1 - сенсорная кнопка, 0 - нет

#define LED_PIN D4      // пин ленты
#define LED_TYPE WS2812 // чип ленты
#define LED_ORDER BGR   // порядок цветов ленты
#define LED_MAX 500     // макс. светодиодов

// имя точки в режиме AP
#define GT_AP_SSID "GyverTwink"
#define GT_AP_PASS "12345678"

// OTA обновление по Wi-Fi (только в режиме подключения к роутеру)
#define GT_OTA 1                // 1 - включить ArduinoOTA, 0 - выключить
//#define GT_OTA_PASS "twink"   // раскомментируй, чтобы задать пароль OTA
//#define DEBUG_SERIAL_GT   // раскомментируй, чтобы включить отладку

// ================== LIBS ==================
#include <ESP8266WiFi.h>
#include <ESP8266mDNS.h>
#include <ArduinoOTA.h>
#include <WiFiUdp.h>
#include <SimplePortal.h>
#include <FastLED.h>
#include <EEManager.h>
#include <EncButton.h>
#include "palettes.h"
#include "Timer.h"

// ================== OBJECTS ==================
WiFiServer server(80);
WiFiUDP udp;
EEManager EEwifi(portalCfg);
CRGB leds[LED_MAX];
CLEDController *strip;
EncButton<EB_TICK, BTN_PIN> btn;
IPAddress myIP;

// ================== EEPROM BLOCKS ==================
struct Cfg {
  uint16_t ledAm = 50;
  bool power = 1;
  byte bright = 100;
  bool autoCh = 0;
  bool rndCh = 0;
  byte prdCh = 1;
  bool turnOff = 0;
  byte offTmr = 60;
};
Cfg cfg;
EEManager EEcfg(cfg);

byte xy[LED_MAX][2];
EEManager EExy(xy);

struct MM {
  byte minY = 0;
  byte maxY = 255;
  byte minX = 0;
  byte maxX = 255;
  byte w = 255;
  byte h = 255;
};
MM mm;
EEManager EEmm(mm);

#define ACTIVE_PALETTES 11
struct Effects {
  bool fav = true;
  byte scale = 50;
  byte speed = 150;
};
Effects effs[ACTIVE_PALETTES * 2];
EEManager EEeff(effs);

// v1.3: последний выбранный вручную эффект (новый блок в конце EEPROM,
// старые блоки и калибровка не сдвигаются)
struct State {
  byte eff = 255;   // 255 - не задан
};
State effState;
EEManager EEstate(effState);

#define GT_PROTO_VER 1          // версия расширенного протокола
#define EFF_AMOUNT (ACTIVE_PALETTES * 2)

// ================== MISC DATA ==================
Timer forceTmr(30000, false);
Timer switchTmr(0, false);
Timer offTmr(60000, false);
bool calibF = false;
byte curEff = 0;
byte forceEff = 0;

// v1.3: макросы определены один раз (конвертер .ino в PlatformIO
// просматривает обе ветки #ifdef и ругался на переопределение)
#ifdef DEBUG_SERIAL_GT
constexpr bool GT_DEBUG = true;
#else
constexpr bool GT_DEBUG = false;
#endif
#define DEBUGLN(x) do { if (GT_DEBUG) Serial.println(x); } while (0)
#define DEBUG(x) do { if (GT_DEBUG) Serial.print(x); } while (0)

// ================== SETUP ==================
void setup() {
#ifdef DEBUG_SERIAL_GT
  Serial.begin(115200);
  DEBUGLN();
#endif
  delay(200);
  if (BTN_TOUCH) btn.setButtonLevel(HIGH);
  startStrip();
  EEPROM.begin(2048); // с запасом!

  // если это первый запуск или щелчок по кнопке, открываем портал
  if (EEwifi.begin(0, 'a') || checkButton()) portalRoutine();

  // создаём точку или подключаемся к AP
  if (portalCfg.mode == WIFI_AP || (portalCfg.mode == WIFI_STA && portalCfg.SSID[0] == '\0')) setupAP();
  else setupSTA();
  DEBUGLN(myIP);

  EEcfg.begin(EEwifi.nextAddr(), 'a');
  EEeff.begin(EEcfg.nextAddr(), 'a');
  EEmm.begin(EEeff.nextAddr(), (uint8_t)LED_MAX);
  EExy.begin(EEmm.nextAddr(), (uint8_t)LED_MAX);
  EEstate.begin(EExy.nextAddr(), 'b');

  switchTmr.setPrd(cfg.prdCh * 60000ul);
  if (cfg.autoCh) switchTmr.restart();
  // v1.3: восстанавливаем выбранный вручную эффект
  if (effState.eff < EFF_AMOUNT) curEff = effState.eff;
  else switchEff();
  cfg.turnOff = false;
  strip->setLeds(leds, cfg.ledAm);
  udp.begin(8888);
  setupNetServices();
}

// ================== LOOP ==================
void loop() {
  button();   // опрос кнопки

  // менеджер епром
  EEcfg.tick();
  EEeff.tick();
  EEstate.tick();
  notifyTick();   // v1.3: OTA, mDNS, push-уведомления подписчику

  parsing();  // парсим udp

  // таймер принудительного показа эффектов
  if (forceTmr.ready()) {
    forceTmr.stop();
    switchEff();
  }

  // форс выключен и настало время менять эффект
  if (!forceTmr.state() && switchTmr.ready()) switchEff();

  // таймер выключения
  if (offTmr.ready()) {
    offTmr.stop();
    cfg.turnOff = false;
    cfg.power = false;
    strip->showLeds(0);
    EEcfg.update();
    DEBUGLN("Off tmr");
  }

  // показываем эффект, если включены
  if (!calibF && cfg.power) effects();
}
