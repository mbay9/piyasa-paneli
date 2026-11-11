# Gösterge sınama protokolü (sonuçlar görülmeden yazıldı)

Amaç: literatürdeki ve sitedeki göstergelerin gerçekten işe yarayıp yaramadığını, çıkan sonuca göre ölçüt değiştirmeden sınamak.
Bu dosya testler çalıştırılmadan önce depoya girer; ölçütler sonradan gevşetilmez. Bir test bu protokolden farklı yapılırsa raporda nedeni yazılır.

## Geçme ölçütleri (tahmin ve strateji iddiaları için)
- K1 İstatistik: Newey-West (HAC) t istatistiği mutlak değerce >= 3,0 (Harvey-Liu-Zhu eşiği). Birden fazla parametre varyantı denenirse hepsi raporlanır, hüküm en iyi değil ortanca varyanta göre verilir.
- K2 Alt dönem tutarlılığı: örneklem iki eşit yarıya bölünür ve ayrıca yayın sonrası dönem ayrılır; işaret iki yarıda da aynı olmalı ve yayın sonrası etki, tüm örneklem etkisinin en az yarısı kadar kalmalı.
- K3 Ekonomik anlam: strateji ise işlem maliyeti sonrası (her giriş-çıkışta 10 baz puan) Sharpe oranı al-tut'tan yüksek ya da en büyük düşüş belirgin düşük. Faktör getirileri brüt olduğu için "maliyet sonrası doğrulanamadı" diye işaretlenir.
- K4 Örneklem dışı: parametreler sabit (önceden belirlenmiş) olmalı; tahmin regresyonlarında genişleyen pencere ile örneklem dışı R2 > 0 ve Clark-West p < 0,05.

## Hüküm sınıfları
- GEÇTİ: K1, K2, K3, K4 hepsi.
- KISMEN: K1 ve K2 sağlanıyor, K3 veya K4'ten biri sağlanmıyor ya da etki yalnızca yayın öncesinde var.
- GEÇMEDİ: K1 sağlanmıyor veya işaret ters.
- TEST EDİLEMEDİ: ücretsiz, hayatta kalma yanlılığından arınmış veri yok ya da örneklem çok küçük. Bu bir "geçti" ya da "geçmedi" değildir.

## Betimleyici göstergeler
Sitedeki bazı göstergeler tahmin iddiası taşımaz (ör. ortalamaya uzaklık). Onlar için yalnızca "tanım tutarlı mı, anlamlı bir şeyi ayırıyor mu" bakılır; hüküm sınıfı yerine "betimleyici" yazılır.

## Veri ve yanlılık kuralları
- Tek hisselik kesit testleri (52 hafta zirvesi, PEAD, kısa pozisyon, analist dağılımı) ücretsiz veride hayatta kalma yanlılığı taşır (bugünün endeks üyeleri). Bu yüzden TEST EDİLEMEDİ sayılır; yerine ileriye dönük kayıt önerilir.
- Piyasa düzeyi testler Ken French veri kütüphanesi (toplam getiri, 1926 sonrası), Yahoo (^GSPC, ^VIX, ^VIX3M, faiz, sektör ETF'leri) ve FRED serileriyle yapılır.
- Veri kaynağına ulaşılamazsa o test atlanır ve raporda "veri alınamadı" yazılır; vekil veri uydurulmaz.
