import sys
import subprocess
import os

# ==========================================
#   OTOMATİK KÜTÜPHANE YÜKLEYİCİ (BAŞLANGIÇ)
# ==========================================
def bagimliliklari_kontrol_et_ve_yukle():
    gerekli_kutuphaneler = {
        "customtkinter": "customtkinter",
        "pynput": "pynput",
        "PIL": "pillow"
    }
    
    eksikler = []
    for modul_adi, pip_adi in gerekli_kutuphaneler.items():
        try:
            __import__(modul_adi)
        except ImportError:
            eksikler.append(pip_adi)
            
    if eksikler:
        print(f"\n[SİSTEM] Eksik kütüphaneler tespit edildi, otomatik yükleniyor: {eksikler}")
        print("-" * 50)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *eksikler])
            print("-" * 50)
            print("[SİSTEM] Tüm kütüphaneler başarıyla yüklendi! Uygulama başlatılıyor...\n")
        except Exception as e:
            print(f"\n❌ Kütüphaneler yüklenirken kritik bir hata oluştu: {e}")
            print("Lütfen internet bağlantınızı kontrol edip tekrar deneyin.")
            input("Çıkmak için ENTER tuşuna basın...")
            sys.exit(1)

bagimliliklari_kontrol_et_ve_yukle()

# ==========================================
#         GEREKLİ KÜTÜPHANELER
# ==========================================
import customtkinter as ctk
import threading
import time
import sqlite3
import json
import zipfile # YENİ: ZIP Paketleme için
from tkinter import filedialog, messagebox
from datetime import datetime
from pynput.keyboard import Listener, Key
from PIL import Image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class TestOtomasyonApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Android Test Otomasyon Merkezi")
        self.geometry("1050x700")
        
        # --- DOSYA VE KLASÖR YOLLARI ---
        self.ana_dizin = os.path.dirname(os.path.abspath(__file__))
        self.db_yolu = os.path.join(self.ana_dizin, "test_merkezi.db")
        self.adb_yolu = os.path.join(self.ana_dizin, "platform-tools", "adb.exe")
        
        self.hata_klasoru = os.path.join(self.ana_dizin, "hata_gorselleri")
        os.makedirs(self.hata_klasoru, exist_ok=True) 

        self.log_klasoru = os.path.join(self.ana_dizin, "test_loglari")
        os.makedirs(self.log_klasoru, exist_ok=True)
        
        # --- KAYIT MOTORU DEĞİŞKENLERİ ---
        self.kayit_aktif = False
        self.popup_acik = False 
        self.gecici_dokunuslar = []
        self.son_dokunus_zamani = 0 
        self.klavye_dinleyici = None
        self.getevent_proc = None

        self.veritabanini_hazirla()

        # --- GRID DÜZENİ ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SOL PANEL (MENÜ) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="TEST PANELİ", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20, padx=10)

        self.btn_kayit_ekran = ctk.CTkButton(self.sidebar_frame, text="Yeni Kayıt Oluştur", command=self.goster_kayit)
        self.btn_kayit_ekran.pack(pady=10, padx=20)

        self.btn_liste_ekran = ctk.CTkButton(self.sidebar_frame, text="Testleri Yönet & Çalıştır", command=self.goster_liste)
        self.btn_liste_ekran.pack(pady=10, padx=20)

        self.btn_rapor_ekran = ctk.CTkButton(self.sidebar_frame, text="📊 Test Raporları", fg_color="#F4A460", text_color="black", hover_color="#d68b49", command=self.goster_raporlar)
        self.btn_rapor_ekran.pack(pady=10, padx=20)

        # --- SAĞ PANEL (İÇERİK) ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.baslangic_ekrani()

    def veritabanini_hazirla(self):
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS case_bazli_testler (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ana_test_adi TEXT, yetkili TEXT, uygulama TEXT, amac TEXT,
            case_adi TEXT, aksiyonlar TEXT, beklenen_xml TEXT)""")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS test_sonuclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ana_test_adi TEXT, tarih TEXT,
            toplam_adim INTEGER, basarili_adim INTEGER, genel_durum TEXT)""")
            
        try:
            cursor.execute("ALTER TABLE test_sonuclari ADD COLUMN detaylar TEXT")
        except sqlite3.OperationalError:
            pass 
            
        conn.commit()
        conn.close()

    def temizle(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def baslangic_ekrani(self):
        self.temizle()
        lbl = ctk.CTkLabel(self.main_frame, text="Hoş geldin Burak!\nSoldan bir işlem seçerek başlayabilirsin.", font=("Arial", 16))
        lbl.pack(expand=True)

    # ==========================================
    #             1. DAHİLİ KAYIT MOTORU 
    # ==========================================
    def goster_kayit(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="📝 Yeni Senaryo Kaydı", font=("Arial", 18, "bold")).pack(pady=10)
        
        self.entry_ad = ctk.CTkEntry(self.main_frame, placeholder_text="Senaryo Adı (Örn: Login)", width=300)
        self.entry_ad.pack(pady=5)
        
        self.entry_yetkili = ctk.CTkEntry(self.main_frame, placeholder_text="Yetkili Kişi", width=300)
        self.entry_yetkili.pack(pady=5)
        
        self.entry_uygulama = ctk.CTkEntry(self.main_frame, placeholder_text="Uygulama Adı", width=300)
        self.entry_uygulama.pack(pady=5)

        self.buton_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.buton_frame.pack(pady=15)

        self.btn_baslat = ctk.CTkButton(self.buton_frame, text="KAYDI BAŞLAT", fg_color="green", hover_color="darkgreen", command=self.kaydi_tetikle)
        self.btn_baslat.grid(row=0, column=0, padx=5)

        self.btn_case_gec = ctk.CTkButton(self.buton_frame, text="Adımı Kaydet (ENTER)", fg_color="#F4A460", text_color="black", state="disabled", command=self.adim_ismi_sor_ve_kaydet)
        self.btn_case_gec.grid(row=0, column=1, padx=5)

        self.btn_bitir = ctk.CTkButton(self.buton_frame, text="Kaydı Bitir (ESC)", fg_color="red", state="disabled", command=self.kaydi_bitir_islem)
        self.btn_bitir.grid(row=0, column=2, padx=5)

        self.log_kutusu = ctk.CTkTextbox(self.main_frame, width=600, height=300)
        self.log_kutusu.pack(pady=10)
        self.log_kutusu.insert("0.0", "Sistem hazır. Bilgileri girip kaydı başlatabilirsiniz...\n")

    def kaydi_tetikle(self):
        self.guncel_test_adi = self.entry_ad.get()
        self.guncel_yetkili = self.entry_yetkili.get()
        self.guncel_uygulama = self.entry_uygulama.get()
        self.guncel_amac = "Arayüz üzerinden test"

        if not self.guncel_test_adi:
            self.log_yaz("\n❌ Hata: Senaryo adı boş olamaz!")
            return

        self.btn_baslat.configure(state="disabled")
        self.btn_case_gec.configure(state="normal")
        self.btn_bitir.configure(state="normal")
        
        self.kayit_aktif = True
        self.popup_acik = False
        self.gecici_dokunuslar = []
        self.son_dokunus_zamani = 0 

        self.log_yaz(f"\n🚀 '{self.guncel_test_adi}' için kayıt dinleyicisi aktif!")
        self.log_yaz("👉 Cihazda işleminizi yapın, adım bittiğinde fiziksel ENTER tuşuna basın.\n")

        threading.Thread(target=self.adb_getevent_dinle, daemon=True).start()
        
        if self.klavye_dinleyici:
            self.klavye_dinleyici.stop()

        self.klavye_dinleyici = Listener(on_press=self.klavye_dinle)
        self.klavye_dinleyici.start()

    def klavye_dinle(self, key):
        if not self.kayit_aktif or self.popup_acik: 
            return 
        
        if key == Key.enter:
            self.after(0, self.adim_ismi_sor_ve_kaydet)
        elif key == Key.esc:
            self.after(0, self.kaydi_bitir_islem)

    def adb_getevent_dinle(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.getevent_proc = subprocess.Popen(
            [self.adb_yolu, "shell", "getevent", "-lt"], 
            stdout=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', bufsize=1, creationflags=c_flags
        )
        x, y = 0, 0
        while self.kayit_aktif:
            line = self.getevent_proc.stdout.readline()
            if not line: break
            
            if "ABS_MT_POSITION_X" in line: x = int(line.split()[-1], 16)
            elif "ABS_MT_POSITION_Y" in line: y = int(line.split()[-1], 16)
            elif "SYN_REPORT" in line and x != 0 and y != 0:
                su_an = time.time()
                if su_an - self.son_dokunus_zamani > 0.5:
                    self.gecici_dokunuslar.append(f"{x},{y}")
                    self.son_dokunus_zamani = su_an
                    self.after(0, lambda px=x, py=y: self.log_yaz(f"🎯 Dokunuş Yakalandı: X:{px}, Y:{py}"))
                x, y = 0, 0

    def adim_ismi_sor_ve_kaydet(self):
        if not self.gecici_dokunuslar:
            self.log_yaz("\n⚠️ Uyarı: Henüz cihaza dokunmadınız!")
            return
        
        kopya_dokunuslar = list(self.gecici_dokunuslar)
        self.gecici_dokunuslar.clear()
        
        self.popup_acik = True
        dialog = ctk.CTkInputDialog(text="Bu adımın adını girin (Örn: Sepete Ekle):", title="Test Adımı İsmi")
        case_adi = dialog.get_input()
        self.popup_acik = False 
        
        if case_adi:
            self.log_yaz(f"\n⏳ '{case_adi}' kaydediliyor, XML çekiliyor lütfen bekleyin...")
            self.update() 
            threading.Thread(target=self.arka_planda_case_kaydet, args=(case_adi, kopya_dokunuslar), daemon=True).start()
        else:
            self.log_yaz("\n❌ İptal edildi, adım kaydedilmedi.")
            self.gecici_dokunuslar = kopya_dokunuslar + self.gecici_dokunuslar

    def arka_planda_case_kaydet(self, case_adi, dokunuslar):
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            
            subprocess.run([self.adb_yolu, "shell", "uiautomator", "dump", "/sdcard/view.xml"], capture_output=True, creationflags=c_flags)
            okuma = subprocess.run([self.adb_yolu, "exec-out", "cat", "/sdcard/view.xml"], capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=c_flags)
            xml_icerik = okuma.stdout if okuma.stdout else ""
                
            aksiyon_str = "|".join(dokunuslar)
            dokunus_sayisi = len(dokunuslar)
            
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO case_bazli_testler VALUES (NULL,?,?,?,?,?,?,?)", 
                         (self.guncel_test_adi, self.guncel_yetkili, self.guncel_uygulama, self.guncel_amac, case_adi, aksiyon_str, xml_icerik))
            conn.commit()
            conn.close()
            
            self.after(0, lambda: self.log_yaz(f"✅ Adım '{case_adi}' BAŞARIYLA KAYDEDİLDİ! ({dokunus_sayisi} Dokunuş)"))
        except Exception as e:
            self.after(0, lambda: self.log_yaz(f"❌ Kayıt hatası: {e}"))

    def kaydi_bitir_islem(self):
        self.kayit_aktif = False
        
        if self.klavye_dinleyici:
            self.klavye_dinleyici.stop()
            self.klavye_dinleyici = None

        if self.getevent_proc and self.getevent_proc.poll() is None:
            self.getevent_proc.terminate()
        
        self.btn_baslat.configure(state="normal")
        self.btn_case_gec.configure(state="disabled")
        self.btn_bitir.configure(state="disabled")
        
        self.log_yaz("\n" + "🟩"*25)
        self.log_yaz("🎉 KAYIT TAMAMLANDI VE MOTOR KAPATILDI!")
        self.log_yaz("🟩"*25 + "\n")

    def log_yaz(self, mesaj):
        self.log_kutusu.insert("end", mesaj + "\n")
        self.log_kutusu.see("end")

    # ==========================================
    #          2. TEST LİSTELEME VE YÖNETİM
    # ==========================================
    def goster_liste(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="🚀 Kayıtlı Testleri Yönet", font=("Arial", 18, "bold")).pack(pady=10)
        
        ust_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ust_frame.pack(pady=5, fill="x", padx=10)

        self.arama_entry = ctk.CTkEntry(ust_frame, placeholder_text="Test Adı veya Uygulama Ara...", width=400)
        self.arama_entry.pack(side="left", padx=10)
        self.arama_entry.bind("<KeyRelease>", self.listeyi_guncelle)

        btn_ice_aktar = ctk.CTkButton(ust_frame, text="📥 Test İçe Aktar (.json)", fg_color="#8e44ad", hover_color="#732d91", command=self.testi_ice_aktar)
        btn_ice_aktar.pack(side="right", padx=10)

        self.test_listesi = ctk.CTkScrollableFrame(self.main_frame, width=800, height=400)
        self.test_listesi.pack(pady=10, padx=10, fill="both", expand=True)

        self.listeyi_guncelle()

    def listeyi_guncelle(self, event=None):
        for widget in self.test_listesi.winfo_children():
            widget.destroy()

        if not os.path.exists(self.db_yolu): return

        arama_metni = self.arama_entry.get().strip()

        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            sorgu = "SELECT DISTINCT ana_test_adi, uygulama, yetkili FROM case_bazli_testler WHERE ana_test_adi LIKE ? OR uygulama LIKE ?"
            cursor.execute(sorgu, (f'%{arama_metni}%', f'%{arama_metni}%'))
            kayitlar = cursor.fetchall()
            conn.close()

            if not kayitlar:
                ctk.CTkLabel(self.test_listesi, text="Eşleşen test bulunamadı.").pack(pady=20)
                return

            for test_adi, uygulama, yetkili in kayitlar:
                satir_frame = ctk.CTkFrame(self.test_listesi, fg_color="#2b2b2b", corner_radius=5)
                satir_frame.pack(fill="x", pady=5, padx=5)

                lbl_bilgi = ctk.CTkLabel(satir_frame, text=f"📂 {test_adi}  |  Uyg: {uygulama}  |  Yazan: {yetkili}", anchor="w", font=("Arial", 13, "bold"))
                lbl_bilgi.pack(side="left", padx=15, pady=10, fill="x", expand=True)

                btn_oynat = ctk.CTkButton(satir_frame, text="▶ Oynat", width=70, fg_color="green", hover_color="darkgreen", command=lambda t=test_adi: self.testi_oynat(t))
                btn_oynat.pack(side="right", padx=5, pady=10)

                btn_paylas = ctk.CTkButton(satir_frame, text="📤 Paylaş", width=70, fg_color="#2980b9", hover_color="#1f618d", command=lambda t=test_adi: self.testi_disa_aktar(t))
                btn_paylas.pack(side="right", padx=5, pady=10)

                btn_duzenle = ctk.CTkButton(satir_frame, text="✏️", width=40, fg_color="#F4A460", text_color="black", hover_color="#d68b49", command=lambda t=test_adi, u=uygulama, y=yetkili: self.duzenle_popup_ac(t, u, y))
                btn_duzenle.pack(side="right", padx=5, pady=10)

                btn_sil = ctk.CTkButton(satir_frame, text="🗑️", width=40, fg_color="#c0392b", hover_color="#962d22", command=lambda t=test_adi: self.testi_sil(t))
                btn_sil.pack(side="right", padx=5, pady=10)
                
        except Exception as e:
            pass

    def testi_disa_aktar(self, test_adi):
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT yetkili, uygulama, amac, case_adi, aksiyonlar, beklenen_xml FROM case_bazli_testler WHERE ana_test_adi = ? ORDER BY id ASC", (test_adi,))
            satirlar = cursor.fetchall()
            conn.close()

            if not satirlar: return

            export_data = {
                "ana_test_adi": test_adi,
                "yetkili": satirlar[0][0],
                "uygulama": satirlar[0][1],
                "amac": satirlar[0][2],
                "caseler": []
            }

            for s in satirlar:
                export_data["caseler"].append({"case_adi": s[3], "aksiyonlar": s[4], "beklenen_xml": s[5]})

            dosya_ismi = f"{test_adi.replace(' ', '_')}_Testi.json"
            dosya_yolu = filedialog.asksaveasfilename(
                defaultextension=".json", filetypes=[("JSON Dosyaları", "*.json")],
                initialfile=dosya_ismi, title="Testi Bilgisayara Kaydet"
            )

            if dosya_yolu:
                with open(dosya_yolu, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("Başarılı", f"Test dışa aktarıldı!\nDosya: {dosya_yolu}")

        except Exception as e:
            messagebox.showerror("Hata", f"Dışa aktarma başarısız: {e}")

    def testi_ice_aktar(self):
        dosya_yolu = filedialog.askopenfilename(filetypes=[("JSON Dosyaları", "*.json")], title="İçe Aktarılacak Testi Seçin")
        if not dosya_yolu: return

        try:
            with open(dosya_yolu, "r", encoding="utf-8") as f: data = json.load(f)

            ana_test_adi = data.get("ana_test_adi", "Bilinmeyen Test") + " (İçe Aktarıldı)"
            yetkili = data.get("yetkili", "Bilinmiyor")
            uygulama = data.get("uygulama", "Bilinmiyor")
            amac = data.get("amac", "Paylaşılan test")
            caseler = data.get("caseler", [])

            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()

            for case in caseler:
                cursor.execute("INSERT INTO case_bazli_testler VALUES (NULL,?,?,?,?,?,?,?)",
                             (ana_test_adi, yetkili, uygulama, amac, case["case_adi"], case["aksiyonlar"], case["beklenen_xml"]))

            conn.commit()
            conn.close()

            self.listeyi_guncelle()
            messagebox.showinfo("Başarılı", f"'{ana_test_adi}' başarıyla sisteme eklendi!")

        except Exception as e:
            messagebox.showerror("Hata", f"Hata: {e}")

    def testi_sil(self, test_adi):
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM case_bazli_testler WHERE ana_test_adi = ?", (test_adi,))
            conn.commit()
            conn.close()
            self.listeyi_guncelle()
        except Exception as e:
            pass

    def duzenle_popup_ac(self, eski_ad, eski_uyg, eski_yetkili):
        popup = ctk.CTkToplevel(self)
        popup.title("Testi Düzenle")
        popup.geometry("400x350")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text=f"'{eski_ad}' Düzenleniyor", font=("Arial", 16, "bold")).pack(pady=15)

        yeni_ad_entry = ctk.CTkEntry(popup, width=250)
        yeni_ad_entry.insert(0, eski_ad)
        yeni_ad_entry.pack(pady=10)

        yeni_uyg_entry = ctk.CTkEntry(popup, width=250)
        yeni_uyg_entry.insert(0, eski_uyg)
        yeni_uyg_entry.pack(pady=10)

        yeni_yetkili_entry = ctk.CTkEntry(popup, width=250)
        yeni_yetkili_entry.insert(0, eski_yetkili)
        yeni_yetkili_entry.pack(pady=10)

        def kaydet():
            y_ad = yeni_ad_entry.get()
            y_uyg = yeni_uyg_entry.get()
            y_yetkili = yeni_yetkili_entry.get()

            if y_ad:
                conn = sqlite3.connect(self.db_yolu)
                cursor = conn.cursor()
                cursor.execute("UPDATE case_bazli_testler SET ana_test_adi = ?, uygulama = ?, yetkili = ? WHERE ana_test_adi = ?", (y_ad, y_uyg, y_yetkili, eski_ad))
                cursor.execute("UPDATE test_sonuclari SET ana_test_adi = ? WHERE ana_test_adi = ?", (y_ad, eski_ad))
                conn.commit()
                conn.close()
                popup.destroy()
                self.listeyi_guncelle()

        ctk.CTkButton(popup, text="💾 Değişiklikleri Kaydet", fg_color="green", hover_color="darkgreen", command=kaydet).pack(pady=20)

    # ==========================================
    #          3. OYNATMA VE LOGCAT MANTIGI
    # ==========================================
    def testi_oynat(self, test_adi):
        self.oynatma_penceresi = ctk.CTkToplevel(self)
        self.oynatma_penceresi.title(f"Test Yürütülüyor: {test_adi}")
        self.oynatma_penceresi.geometry("600x450")
        self.oynatma_penceresi.attributes("-topmost", True)
        
        lbl_baslik = ctk.CTkLabel(self.oynatma_penceresi, text=f"🚀 {test_adi} Testi Çalışıyor", font=("Arial", 16, "bold"))
        lbl_baslik.pack(pady=10)

        self.canli_log = ctk.CTkTextbox(self.oynatma_penceresi, width=560, height=350, font=("Consolas", 13))
        self.canli_log.pack(padx=10, pady=5, fill="both", expand=True)
        self.canli_log.insert("end", "[SİSTEM] ADB bağlantısı kuruluyor...\n\n")

        threading.Thread(target=self.arka_planda_oynat, args=(test_adi,), daemon=True).start()

    def arka_planda_oynat(self, test_adi):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        
        def ekrana_yaz(mesaj):
            self.canli_log.insert("end", mesaj + "\n")
            self.canli_log.see("end")

        zaman_damgasi = int(time.time())
        log_dosya_adi = f"log_{test_adi.replace(' ', '_')}_{zaman_damgasi}.txt"
        log_yolu = os.path.join(self.log_klasoru, log_dosya_adi)
        
        subprocess.run([self.adb_yolu, "logcat", "-c"], creationflags=c_flags)
        log_dosyasi = open(log_yolu, "w", encoding="utf-8")
        log_proc = subprocess.Popen([self.adb_yolu, "logcat", "-v", "threadtime"], stdout=log_dosyasi, creationflags=c_flags)

        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT case_adi, aksiyonlar, beklenen_xml FROM case_bazli_testler WHERE ana_test_adi = ? ORDER BY id ASC", (test_adi,))
            cases = cursor.fetchall()

            if not cases:
                ekrana_yaz("❌ Bu teste ait hiçbir case (adım) bulunamadı!")
                log_proc.terminate()
                log_dosyasi.close()
                conn.close()
                return

            toplam_adim = len(cases)
            basarili_adim = 0
            adim_raporlari = []

            for c_adi, aksiyonlar, ref_xml in cases:
                dokunuslar = [n for n in aksiyonlar.split("|") if n]
                ekrana_yaz(f"⏳ '{c_adi}' adımı oynatılıyor...")
                
                for nokta in dokunuslar:
                    x, y = nokta.split(",")
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", x, y], creationflags=c_flags)
                    time.sleep(0.2) 
                
                time.sleep(1.0) 

                ekrana_yaz(f"🔍 '{c_adi}' denetleniyor...")
                
                subprocess.run([self.adb_yolu, "shell", "uiautomator", "dump", "/sdcard/check.xml"], capture_output=True, creationflags=c_flags)
                okuma = subprocess.run([self.adb_yolu, "exec-out", "cat", "/sdcard/check.xml"], capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=c_flags)
                su_anki = okuma.stdout if okuma.stdout else ""
                
                if su_anki:
                    fark = abs(len(su_anki) - len(ref_xml)) / len(ref_xml) if len(ref_xml) > 0 else 1
                    
                    if fark > 0.3:
                        ekrana_yaz(f"❌ {c_adi} BAŞARISIZ! (Fark: %{int(fark*100)})\n" + "-"*40)
                        
                        foto_isim = f"hata_{test_adi.replace(' ', '_')}_{c_adi.replace(' ', '_')}_{int(time.time())}.png"
                        foto_yol = os.path.join(self.hata_klasoru, foto_isim)
                        
                        ekrana_yaz("📸 Hata fotoğrafı çekiliyor...")
                        subprocess.run([self.adb_yolu, "shell", "screencap", "-p", "/sdcard/hata.png"], capture_output=True, creationflags=c_flags)
                        subprocess.run([self.adb_yolu, "pull", "/sdcard/hata.png", foto_yol], capture_output=True, creationflags=c_flags)
                        
                        adim_raporlari.append(f"❌ {c_adi} - BAŞARISIZ (Fark: %{int(fark*100)}) | IMG:{foto_yol}")
                    else:
                        ekrana_yaz(f"✅ {c_adi} BAŞARILI! (Fark: %{int(fark*100)})\n" + "-"*40)
                        basarili_adim += 1
                        adim_raporlari.append(f"✅ {c_adi} - BAŞARILI (Fark: %{int(fark*100)})")
                else:
                    ekrana_yaz(f"⚠️ {c_adi} denetlenemedi (XML çekilemedi).\n" + "-"*40)
                    adim_raporlari.append(f"⚠️ {c_adi} - OKUNAMADI")
                    
            ekrana_yaz("\n🏁 BÜTÜN TEST ADIMLARI TAMAMLANDI!")

            log_proc.terminate()
            log_dosyasi.close()
            adim_raporlari.append(f"📄 LOG DOSYASI | LOG:{log_yolu}")

            genel_durum = "BAŞARILI" if basarili_adim == toplam_adim else "BAŞARISIZ"
            tarih_saat = datetime.now().strftime("%d-%m-%Y %H:%M")
            detaylar_str = "\n".join(adim_raporlari)
            
            try:
                cursor.execute("INSERT INTO test_sonuclari (ana_test_adi, tarih, toplam_adim, basarili_adim, genel_durum, detaylar) VALUES (?,?,?,?,?,?)", 
                             (test_adi, tarih_saat, toplam_adim, basarili_adim, genel_durum, detaylar_str))
            except Exception:
                cursor.execute("INSERT INTO test_sonuclari VALUES (NULL,?,?,?,?,?)", 
                             (test_adi, tarih_saat, toplam_adim, basarili_adim, genel_durum))
                             
            conn.commit()
            conn.close()

            ekrana_yaz(f"\n💾 Test raporu ve Logcat kaydedildi! ({basarili_adim}/{toplam_adim} Adım Başarılı)")
            
        except Exception as e:
            log_proc.terminate()
            log_dosyasi.close()
            ekrana_yaz(f"\n❌ Kritik Hata: {str(e)}")

    # ==========================================
    #          4. TEST RAPORLARI VE DETAY PENCERESİ 
    # ==========================================
    def goster_raporlar(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="📊 Geçmiş Test Sonuç Raporları", font=("Arial", 18, "bold")).pack(pady=10)
        
        ust_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ust_frame.pack(pady=5, fill="x", padx=10)

        self.arama_rapor_entry = ctk.CTkEntry(ust_frame, placeholder_text="Raporlarda Test Adı Ara...", width=400)
        self.arama_rapor_entry.pack(side="left", padx=10)
        self.arama_rapor_entry.bind("<KeyRelease>", self.rapor_listeyi_guncelle)

        self.rapor_listesi = ctk.CTkScrollableFrame(self.main_frame, width=800, height=450)
        self.rapor_listesi.pack(pady=10, padx=10, fill="both", expand=True)
        
        self.rapor_listeyi_guncelle()

    def rapor_listeyi_guncelle(self, event=None):
        for widget in self.rapor_listesi.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            
            arama_metni = self.arama_rapor_entry.get().strip() if hasattr(self, 'arama_rapor_entry') else ""
            sorgu = "SELECT id, ana_test_adi, tarih, toplam_adim, basarili_adim, genel_durum, detaylar FROM test_sonuclari WHERE ana_test_adi LIKE ? ORDER BY id DESC"
            
            cursor.execute(sorgu, (f'%{arama_metni}%',))
            raporlar = cursor.fetchall()
            conn.close()

            if not raporlar:
                ctk.CTkLabel(self.rapor_listesi, text="Arama sonucunda rapor bulunamadı.", text_color="yellow").pack(pady=20)
                return

            for r_id, test_adi, tarih, toplam, basarili, durum, detaylar in raporlar:
                arka_plan_rengi = "darkgreen" if durum == "BAŞARILI" else "#962d22"
                satir = ctk.CTkFrame(self.rapor_listesi, fg_color=arka_plan_rengi, corner_radius=5)
                satir.pack(fill="x", pady=5, padx=5)

                bilgi_metni = f"🕒 {tarih}   |   📂 {test_adi}   |   Başarı: {basarili}/{toplam}"
                ctk.CTkLabel(satir, text=bilgi_metni, font=("Arial", 13, "bold")).pack(side="left", padx=15, pady=10)
                
                btn_sil = ctk.CTkButton(satir, text="🗑️ Sil", width=60, fg_color="#c0392b", hover_color="#962d22", command=lambda idx=r_id: self.raporu_sil(idx))
                btn_sil.pack(side="right", padx=5, pady=10)

                # YENİ: ZIP PAYLAŞ BUTONU
                btn_paylas = ctk.CTkButton(satir, text="📤 Paylaş (ZIP)", width=100, fg_color="#2980b9", hover_color="#1f618d", command=lambda t=test_adi, dt=tarih, tp=toplam, b=basarili, dr=durum, d=detaylar: self.raporu_zip_paylas(t, dt, tp, b, dr, d))
                btn_paylas.pack(side="right", padx=5, pady=10)

                btn_detay = ctk.CTkButton(satir, text="🔍 Detaylar", width=80, fg_color="#1f538d", hover_color="#14375e", command=lambda t=test_adi, dt=tarih, d=detaylar: self.detay_popup_ac(t, dt, d))
                btn_detay.pack(side="right", padx=5, pady=10)

        except Exception as e:
            ctk.CTkLabel(self.rapor_listesi, text=f"❌ Rapor okuma hatası: {e}", text_color="red").pack(pady=20)

    def raporu_sil(self, rapor_id):
        cevap = messagebox.askyesno("Onay", "Bu test raporunu kalıcı olarak silmek istediğinize emin misiniz?\n(Fotoğraf ve log dosyaları da diskten silinecektir.)")
        if not cevap: return

        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            
            cursor.execute("SELECT detaylar FROM test_sonuclari WHERE id = ?", (rapor_id,))
            kayit = cursor.fetchone()
            if kayit and kayit[0]:
                for satir in kayit[0].split("\n"):
                    if "| IMG:" in satir:
                        yol = satir.split("| IMG:")[1].strip()
                        if os.path.exists(yol): os.remove(yol)
                    elif "| LOG:" in satir:
                        yol = satir.split("| LOG:")[1].strip()
                        if os.path.exists(yol): os.remove(yol)

            cursor.execute("DELETE FROM test_sonuclari WHERE id = ?", (rapor_id,))
            conn.commit()
            conn.close()
            self.rapor_listeyi_guncelle()
            
        except Exception as e:
            messagebox.showerror("Hata", f"Rapor silinirken hata oluştu: {e}")

    # ==========================================
    #     YENİ: ZIP HALİNDE RAPOR PAYLAŞMA
    # ==========================================
    def raporu_zip_paylas(self, test_adi, tarih, toplam, basarili, durum, detaylar):
        dosya_tarih = tarih.replace(":", "-").replace(" ", "_")
        zip_ismi = f"Rapor_{test_adi.replace(' ', '_')}_{dosya_tarih}.zip"
        
        zip_yolu = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP Dosyaları", "*.zip")],
            initialfile=zip_ismi,
            title="Raporu ZIP Olarak Kaydet (Ekibe Gönder)"
        )

        if not zip_yolu: return

        try:
            rapor_icerik = "="*55 + "\n"
            rapor_icerik += f"           OTOMASYON TEST SONUÇ RAPORU\n"
            rapor_icerik += "="*55 + "\n\n"
            rapor_icerik += f"📌 Test Adı       : {test_adi}\n"
            rapor_icerik += f"🕒 Çalışma Tarihi : {tarih}\n"
            rapor_icerik += f"📊 Başarı Oranı   : {basarili} / {toplam} Adım Başarılı\n"
            rapor_icerik += f"🎯 Genel Durum    : {durum}\n\n"
            rapor_icerik += "--- ADIM BAZLI DETAYLAR ---\n"
            
            eklenecek_dosyalar = []
            
            if detaylar:
                for satir in detaylar.split("\n"):
                    if "| IMG:" in satir:
                        metin, yol = satir.split("| IMG:")
                        yol = yol.strip()
                        rapor_icerik += metin.strip() + f" (Hata Görseli Zip İçinde: {os.path.basename(yol)})\n"
                        if os.path.exists(yol):
                            eklenecek_dosyalar.append(yol)
                    elif "| LOG:" in satir:
                        metin, yol = satir.split("| LOG:")
                        yol = yol.strip()
                        rapor_icerik += metin.strip() + f" (Log Dosyası Zip İçinde: {os.path.basename(yol)})\n"
                        if os.path.exists(yol):
                            eklenecek_dosyalar.append(yol)
                    else:
                        rapor_icerik += satir + "\n"
            else:
                rapor_icerik += "Detay bulunamadı.\n"
                
            rapor_icerik += "\n" + "="*55 + "\n"

            with zipfile.ZipFile(zip_yolu, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 1. Rapor txt dosyasını yazdır
                zipf.writestr(f"Test_Sonuc_Raporu_{dosya_tarih}.txt", rapor_icerik)
                
                # 2. Resim ve logları arşive ekle
                for dosya in set(eklenecek_dosyalar): 
                    zipf.write(dosya, arcname=os.path.basename(dosya))
            
            messagebox.showinfo("Başarılı", f"Rapor, Log dosyası ve Hata görüntüleri başarıyla ZIP olarak paketlendi!\n\nDosya: {zip_yolu}")
        except Exception as e:
            messagebox.showerror("Hata", f"Rapor paketlenirken hata oluştu: {e}")

    # ----------------------------------------
    def detay_popup_ac(self, test_adi, tarih, detaylar):
        popup = ctk.CTkToplevel(self)
        popup.title("Test Adım Detayları")
        popup.geometry("550x650") 
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text=f"📂 {test_adi}\n🕒 {tarih}", font=("Arial", 16, "bold")).pack(pady=10)
        
        scroll_alan = ctk.CTkScrollableFrame(popup, width=500, height=550)
        scroll_alan.pack(padx=10, pady=10, fill="both", expand=True)
        
        if detaylar:
            for satir in detaylar.split("\n"):
                if "| IMG:" in satir:
                    metin_kismi, foto_yolu = satir.split("| IMG:")
                    foto_yolu = foto_yolu.strip()
                    ctk.CTkLabel(scroll_alan, text=metin_kismi.strip(), font=("Arial", 14, "bold"), text_color="#ff4d4d").pack(pady=(15, 5), anchor="w", padx=10)
                    
                    if os.path.exists(foto_yolu):
                        try:
                            orijinal_resim = Image.open(foto_yolu)
                            oran = 300 / orijinal_resim.width
                            yeni_boyut = (300, int(orijinal_resim.height * oran))
                            
                            ctk_img = ctk.CTkImage(light_image=orijinal_resim, dark_image=orijinal_resim, size=yeni_boyut)
                            lbl_resim = ctk.CTkLabel(scroll_alan, image=ctk_img, text="")
                            lbl_resim.pack(pady=5, anchor="w", padx=30)
                        except Exception as e:
                            ctk.CTkLabel(scroll_alan, text=f"⚠️ Resim Yüklenemedi: {e}", text_color="yellow").pack(anchor="w", padx=30)
                    else:
                        ctk.CTkLabel(scroll_alan, text="⚠️ Ekran görüntüsü silinmiş veya bulunamadı.", text_color="yellow").pack(anchor="w", padx=30)
                
                elif "| LOG:" in satir:
                    metin_kismi, log_yolu = satir.split("| LOG:")
                    log_yolu = log_yolu.strip()
                    
                    if os.path.exists(log_yolu):
                        ctk.CTkButton(scroll_alan, text="📄 Tüm Cihaz Logunu (Logcat) Göster", fg_color="#8e44ad", hover_color="#732d91", command=lambda p=log_yolu: os.startfile(p)).pack(pady=(20, 10), padx=30, fill="x")
                    else:
                        ctk.CTkLabel(scroll_alan, text="⚠️ Log dosyası silinmiş.", text_color="yellow").pack(anchor="w", padx=30)
                else:
                    renk = "lightgreen" if "✅" in satir else ("white" if "⚠️" in satir else "white")
                    ctk.CTkLabel(scroll_alan, text=satir.strip(), font=("Arial", 14, "bold"), text_color=renk).pack(pady=(15, 5), anchor="w", padx=10)
        else:
            ctk.CTkLabel(scroll_alan, text="⚠️ Adım detayı bulunmuyor.").pack(pady=20)

if __name__ == "__main__":
    app = TestOtomasyonApp()
    app.mainloop()