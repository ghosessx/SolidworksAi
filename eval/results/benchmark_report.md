# SolidAI CAD Reliability & Benchmark Report

**Çalıştırma Modu:** HEADLESS (MockCADEngine)  
**Tarih:** 2026-10-17 16:58:42  
**Genel Durum:** ✅ TÜM TESTLER BAŞARILI

## Test Sonuçları Tablosu

| Test ID | Test Adı | Durum | Süre (ms) | Gövde Sayısı | Hacim | Beklenen Hacim | Notlar |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE_1_PRISM | 5x5x5 mm Küp / Prizma | PASS | 0.3 | 1/1 | 125.0 mm3 | 120 - 130 mm3 | OK |
| CASE_2_FLANGE | 6 Delikli Standart Boru Flanşı | PASS | 0.4 | 1/1 | 191275.9 mm3 | 180000 - 200000 mm3 | OK |
| CASE_3_L_BRACKET | NEMA 17 Step Motor L-Montaj Braketi | PASS | 0.9 | 1/1 | 15605.5 mm3 | 13000 - 17500 mm3 | OK |
| CASE_4_STEPPED_SHAFT | 3 Kademeli Mil | PASS | 0.2 | 1/1 | 45741.6 mm3 | 44000 - 47500 mm3 | OK |
| CASE_5_PILLOW_BLOCK | Yataklama Braketi (Pillow Block) | PASS | 0.6 | 1/1 | 605954.6 mm3 | 450000 - 650000 mm3 | OK |
| CASE_6_SHIFT_FORK | Vites Çatalı ve Mafsal (Practice 36) | PASS | 0.5 | 1/1 | 87839.8 mm3 | 80000 - 120000 mm3 | OK |
| CASE_7_QUADCOPTER_FRAME | Quadcopter 240 mm X-Frame Şase Plakası | PASS | 1.1 | 1/1 | 43439.6 mm3 | 35000 - 55000 mm3 | OK |
| FAIL_1_UNKNOWN_OPERATION | Bilinmeyen CAD İşlemi Enjeksiyonu | PASS | 1.0 | N/A | N/A | N/A | Pydantic caught: 1 validation error for CADPlan
adimlar.0.islem
  Value error... |
| FAIL_2_EMPTY_SKETCH_EXTRUSION | Boş Çizim Katılama Enjeksiyonu | PASS | 1.0 | N/A | N/A | N/A | Simulator caught: Step 3 (extrude_boss): Sketch contains no 2D profiles or geo... |
| FAIL_3_REVOLVE_WITHOUT_AXIS | Eksensiz Döndürme Enjeksiyonu | PASS | 1.0 | N/A | N/A | N/A | Simulator caught: Step 4 (revolve_boss): A revolution requires an axis of revo... |