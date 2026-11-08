// v1.3: OTA, mDNS и push-уведомления для Home Assistant

bool netReady = false;          // OTA и mDNS запущены (только STA)

// подписчик на уведомления (обычно Home Assistant)
IPAddress subIP;
uint16_t subPort = 0;
uint32_t subTmr = 0;
#define SUB_TIMEOUT (5 * 60000ul)   // подписка живёт 5 минут после последнего запроса

void setupNetServices() {
  if (WiFi.getMode() != WIFI_STA) return;

  char host[20];
  snprintf(host, sizeof(host), "gyvertwink-%06x", ESP.getChipId());

#if GT_OTA
  ArduinoOTA.setHostname(host);
#ifdef GT_OTA_PASS
  ArduinoOTA.setPassword(GT_OTA_PASS);
#endif
  ArduinoOTA.onStart([]() {
    strip->clearLedData();
    strip->showLeds(0);
  });
  ArduinoOTA.begin();   // запускает и mDNS с этим именем
#else
  MDNS.begin(host);
#endif
  // по этой службе Home Assistant находит гирлянду (zeroconf)
  MDNS.addService("gyvertwink", "udp", 8888);
  MDNS.addServiceTxt("gyvertwink", "udp", "proto", String(GT_PROTO_VER));
  netReady = true;
}

void netTick() {
  if (!netReady) return;
#if GT_OTA
  ArduinoOTA.handle();
#endif
  MDNS.update();
}

void subscribe() {
  subIP = udp.remoteIP();
  subPort = udp.remotePort();
  subTmr = millis();
}

// эффект, который сейчас реально показывается
byte shownEff() {
  return forceTmr.state() ? forceEff : curEff;
}

// {1, ...} - тот же формат, что ответ на запрос настроек (10 байт данных)
byte fillSettings(byte* answ) {
  answ[0] = 1;
  answ[1] = cfg.ledAm / 100;
  answ[2] = cfg.ledAm % 100;
  answ[3] = cfg.power;
  answ[4] = cfg.bright;
  answ[5] = cfg.autoCh;
  answ[6] = cfg.rndCh;
  answ[7] = cfg.prdCh;
  answ[8] = cfg.turnOff;
  answ[9] = cfg.offTmr;
  return 10;
}

// {5, proto, эффект, кол-во эффектов, mac[6]} - 10 байт данных
// (приложение GyverTwink падает на ответах длиннее 10 байт данных)
byte fillExtInfo(byte* answ) {
  answ[0] = 5;
  answ[1] = GT_PROTO_VER;
  answ[2] = shownEff();
  answ[3] = EFF_AMOUNT;
  uint8_t mac[6];
  WiFi.macAddress(mac);
  for (byte i = 0; i < 6; i++) answ[4 + i] = mac[i];
  return 10;
}

void sendTo(IPAddress ip, uint16_t port, byte* data, byte size) {
  udp.beginPacket(ip, port);
  udp.write("GT");
  udp.write(data, size);
  udp.endPacket();
}

// раз в 200 мс сравниваем состояние и шлём подписчику, если изменилось
void notifyTick() {
  netTick();

  static uint32_t tmr;
  static uint32_t lastHash = 0;
  if (millis() - tmr < 200) return;
  tmr = millis();
  if (!subPort) return;
  if (millis() - subTmr > SUB_TIMEOUT) {
    subPort = 0;
    return;
  }

  byte s[10], e[10];
  fillSettings(s);
  fillExtInfo(e);
  uint32_t h = 2166136261ul;   // FNV-1a
  for (byte i = 0; i < 10; i++) h = (h ^ s[i]) * 16777619ul;
  h = (h ^ e[2]) * 16777619ul;
  if (h == lastHash) return;
  lastHash = h;
  sendTo(subIP, subPort, s, 10);
  sendTo(subIP, subPort, e, 10);
}
