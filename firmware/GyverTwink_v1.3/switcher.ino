void switchEff() {
  // v1.3: если ни один эффект не в избранном - просто следующий
  // (раньше здесь был вечный цикл и гирлянда зависала)
  bool anyFav = false;
  for (byte i = 0; i < ACTIVE_PALETTES * 2; i++) {
    if (effs[i].fav) {
      anyFav = true;
      break;
    }
  }
  if (!anyFav) {
    if (++curEff >= ACTIVE_PALETTES * 2) curEff = 0;
    return;
  }

  // поиск favorite эффектов
  while (true) {
    if (cfg.rndCh) curEff = random(0, ACTIVE_PALETTES * 2);
    else {
      if (++curEff >= ACTIVE_PALETTES * 2) curEff = 0;
    }
    if (effs[curEff].fav) break;
  }
  DEBUG("switch to: ");
  DEBUGLN(curEff);
}
