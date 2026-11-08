#define MAX_UDP_PACKET 30
byte ubuf[MAX_UDP_PACKET + 1];   // v1.3: +1 под завершающий ноль

void reply(byte* data, byte size) {
  sendTo(udp.remoteIP(), udp.remotePort(), data, size);
}

void parsing() {
  static uint32_t tmr;
  static byte lastCmd = 255, lastSub = 255;
  if (udp.parsePacket()) {
    int n = udp.read(ubuf, MAX_UDP_PACKET);
    if (n < 3) return;
    ubuf[n] = 0;
    if (ubuf[0] != 'G' || ubuf[1] != 'T') return;

    // "антидребезг" приёма: слайдеры приложения шлют пакеты пачкой.
    // v1.3: глушим только повтор той же команды, разные команды проходят сразу
    if (millis() - tmr < 50 && ubuf[2] == lastCmd && ubuf[3] == lastSub) return;
    tmr = millis();
    lastCmd = ubuf[2];
    lastSub = ubuf[3];

    byte answ[10];

    switch (ubuf[2]) {
      case 0:   // запрос IP
        delay(myIP[3] * 2);
        answ[0] = 0;
        answ[1] = myIP[3];
        reply(answ, 2);
        break;

      case 1:   // запрос настроек
        // v1.3: {1, 1} - запрос + подписка на уведомления
        if (n > 3 && ubuf[3] == 1) subscribe();
        reply(answ, fillSettings(answ));
        break;

      case 2:   // приём настроек
        forceTmr.stop();
        switch (ubuf[3]) {
          case 0: cfg.ledAm = ubuf[4] * 100 + ubuf[5];
            cfg.ledAm = constrain(cfg.ledAm, 1, LED_MAX);
            strip->setLeds(leds, cfg.ledAm);
            break;
          case 1: cfg.power = ubuf[4];
            break;
          case 2: cfg.bright = ubuf[4];
            break;
          case 3: cfg.autoCh = ubuf[4];
            if (cfg.autoCh) switchTmr.restart();
            else switchTmr.stop();
            break;
          case 4: cfg.rndCh = ubuf[4];
            break;
          case 5: cfg.prdCh = constrain(ubuf[4], 1, 255);
            switchTmr.setPrd(cfg.prdCh * 60000ul);
            if (cfg.autoCh) switchTmr.restart();
            break;
          case 6:   // нехт эффект
            switchEff();
            if (cfg.autoCh) switchTmr.restart();
            return;
            break;
          case 7:
            cfg.turnOff = ubuf[4];
            if (cfg.turnOff) offTmr.restart();
            else offTmr.stop();
            break;
          case 8:
            cfg.offTmr = constrain(ubuf[4], 1, 255);
            offTmr.setPrd(cfg.offTmr * 60000ul);
            if (cfg.turnOff) offTmr.restart();
            break;
        }
        if (!cfg.power) strip->showLeds(0);
        EEcfg.update();
        break;

      case 3:
        switch (ubuf[3]) {
          case 0:   // запуск калибровки
            DEBUGLN("Calibration start");
            calibF = true;
            strip->clearLedData();
            strip->showLeds(0);
            break;

          case 1:   // следующий лед
            {
              int curLed = ubuf[4] * 100 + ubuf[5];
              if (curLed > 0 && curLed <= LED_MAX) {
                xy[curLed - 1][0] = ubuf[6];
                xy[curLed - 1][1] = ubuf[7];
              }
              strip->clearLedData();
              if (curLed < LED_MAX) leds[curLed] = CRGB::White;
              strip->showLeds(200);
            }
            break;

          case 2:   // калибровка окончена
            DEBUGLN("Finished");
            calibF = false;
            strip->clearLedData();
            strip->showLeds(0);
            EExy.updateNow();

            mm.minY = 255;
            mm.maxY = 0;
            mm.minX = 255;
            mm.maxX = 0;
            for (int i = 0; i < cfg.ledAm; i++) {
              mm.minX = min(mm.minX, xy[i][0]);
              mm.maxX = max(mm.maxX, xy[i][0]);
              mm.minY = min(mm.minY, xy[i][1]);
              mm.maxY = max(mm.maxY, xy[i][1]);
            }
            mm.w = mm.maxX - mm.minX;
            mm.h = mm.maxY - mm.minY;
            EEmm.updateNow();
            break;
        }
        break;

      case 4:   // управление эффектами (приложение: показ эффекта на 30 секунд)
        if (ubuf[3] == 0 && ubuf[4] >= EFF_AMOUNT) return;
        forceTmr.restart();
        EEeff.update();
        switch (ubuf[3]) {
          case 0:   // выбор эффекта в дропе
            forceEff = ubuf[4];
            answ[0] = 4;
            answ[1] = effs[forceEff].fav;
            answ[2] = effs[forceEff].scale;
            answ[3] = effs[forceEff].speed;
            reply(answ, 4);
            break;
          case 1:   // флажок избранное
            effs[forceEff].fav = ubuf[4];
            break;
          case 2:   // масштаб
            effs[forceEff].scale = ubuf[4];
            break;
          case 3:   // скорость
            effs[forceEff].speed = ubuf[4];
            break;
        }
        break;

      // ================= v1.3: расширенный протокол =================
      case 5:   // {5} - расширенная информация
        reply(answ, fillExtInfo(answ));
        break;

      case 6:   // {6, n} - выбрать эффект насовсем
        if (ubuf[3] >= EFF_AMOUNT) return;
        forceTmr.stop();
        curEff = ubuf[3];
        if (cfg.autoCh) switchTmr.restart();
        effState.eff = curEff;
        EEstate.update();
        reply(answ, fillExtInfo(answ));
        break;

      case 7:   // {7, n} - параметры эффекта, без принудительного показа
        if (ubuf[3] >= EFF_AMOUNT) return;
        answ[0] = 7;
        answ[1] = ubuf[3];
        answ[2] = effs[ubuf[3]].fav;
        answ[3] = effs[ubuf[3]].scale;
        answ[4] = effs[ubuf[3]].speed;
        reply(answ, 5);
        break;

      case 8:   // {8, n, fav, scale, speed} - записать параметры эффекта
        if (n < 7 || ubuf[3] >= EFF_AMOUNT) return;
        effs[ubuf[3]].fav = ubuf[4];
        effs[ubuf[3]].scale = ubuf[5];
        effs[ubuf[3]].speed = ubuf[6];
        EEeff.update();
        answ[0] = 7;
        answ[1] = ubuf[3];
        answ[2] = effs[ubuf[3]].fav;
        answ[3] = effs[ubuf[3]].scale;
        answ[4] = effs[ubuf[3]].speed;
        reply(answ, 5);
        break;
    }
  }
}
