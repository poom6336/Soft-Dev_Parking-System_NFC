'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { QRCodeSVG } from 'qrcode.react';
import { 
  CheckCircle2, Clock, CreditCard, AlertCircle, RefreshCw, 
  Car, Nfc, ShieldCheck, History, Camera, ArrowRight, Lock, 
  Copy, Download, MapPin, Receipt, Check, PhoneCall, HelpCircle, AlertTriangle
} from 'lucide-react';

function PaymentContent() {
  const searchParams = useSearchParams();
  const uid = searchParams.get('uid') || 'A1B2C3D4';
  const licensePlate = searchParams.get('plate') || 'กท-1234';
  const zone = searchParams.get('zone') || 'ชั้น 2 - โซน B14';

  const [status, setStatus] = useState<'parked' | 'paying' | 'success' | 'receipt' | 'sos'>('parked');
  const [payCountdown, setPayCountdown] = useState(300); // 5 นาทีสำหรับจ่ายเงิน
  const [exitCountdown, setExitCountdown] = useState(900); // 15 นาทีสำหรับขับออก
  const [parkedSeconds, setParkedSeconds] = useState(5120); // จำลองเวลาจอด
  const [copied, setCopied] = useState(false);
  const [extendedTime, setExtendedTime] = useState(false);
  const [showBreakdown, setShowBreakdown] = useState(false);

  const hoursParked = Math.ceil(parkedSeconds / 3600);
  const ratePerHour = 20;
  const amount = hoursParked * ratePerHour;

  // นับเวลาจอดจริง
  useEffect(() => {
    if (status === 'success' || status === 'receipt' || status === 'sos') return;
    const interval = setInterval(() => {
      setParkedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [status]);

  // นับถอยหลังจ่ายเงิน
  useEffect(() => {
    if (status !== 'paying' || payCountdown <= 0) return;
    const timer = setInterval(() => {
      setPayCountdown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [status, payCountdown]);

  // นับถอยหลังเวลาขับออก (Grace Period)
  useEffect(() => {
    if (status !== 'success' || exitCountdown <= 0) return;
    const timer = setInterval(() => {
      setExitCountdown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [status, exitCountdown]);

  const formatDuration = (totalSeconds: number) => {
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    return `${hrs} ชม. ${mins} นาที ${secs} วิ`;
  };

  const formatClock = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleCopyPromptPay = () => {
    navigator.clipboard.writeText(`00020101021229370016A000000677010111031500000000000005802TH5303764540${amount}.005802TH6304`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExtendGracePeriod = () => {
    if (!extendedTime) {
      setExitCountdown((prev) => prev + 300); // เพิ่ม 5 นาที (300 วิ)
      setExtendedTime(true);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4 font-sans">
      <div className="w-full max-w-md space-y-4">
        
        {/* Header Branding & SOS Button */}
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center gap-2">
            <div className="bg-amber-400/10 p-2 rounded-xl text-amber-400 border border-amber-400/20">
              <Nfc className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-amber-400 tracking-wider uppercase">NFC SMART PASS</h1>
              <p className="text-xs text-slate-400">Automated Parking System</p>
            </div>
          </div>
          
          {/* Quick SOS Trigger */}
          <button 
            onClick={() => setStatus('sos')}
            className="text-xs bg-rose-500/10 text-rose-400 border border-rose-500/30 px-2.5 py-1.5 rounded-full font-semibold flex items-center gap-1 hover:bg-rose-500/20 transition"
          >
            <PhoneCall className="w-3.5 h-3.5 animate-bounce" /> SOS ช่วยเหลือ
          </button>
        </div>

        {/* Card 1: Virtual NFC Pass */}
        <div className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-amber-500/30 rounded-2xl p-6 shadow-2xl">
          <div className="flex justify-between items-start mb-3">
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-widest font-semibold">Registered Member</p>
              <h2 className="text-2xl font-extrabold text-white mt-0.5">{licensePlate}</h2>
            </div>
            <div className="bg-amber-400/20 text-amber-300 border border-amber-400/40 text-[10px] font-bold px-2.5 py-1 rounded-md tracking-wider uppercase">
              VIP MEMBER
            </div>
          </div>

          {/* Location Spot Badge */}
          <div className="inline-flex items-center gap-1.5 bg-slate-950/80 border border-slate-700 px-3 py-1.5 rounded-lg text-xs text-amber-300 mb-2">
            <MapPin className="w-3.5 h-3.5 text-amber-400" />
            <span>ตำแหน่งจอด: <strong>{zone}</strong></span>
          </div>

          <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-800 text-xs">
            <div>
              <span className="text-slate-500 block text-[10px] uppercase">NFC UID</span>
              <span className="font-mono text-amber-400 font-bold text-sm">{uid}</span>
            </div>
            <div className="text-right">
              <span className="text-slate-500 block text-[10px] uppercase">Parking Status</span>
              {status === 'success' || status === 'receipt' ? (
                <span className="text-emerald-400 font-bold flex items-center gap-1 justify-end">
                  <ShieldCheck className="w-3.5 h-3.5" /> EXIT AUTHORIZED
                </span>
              ) : (
                <span className="text-blue-400 font-bold flex items-center gap-1 justify-end">
                  <Car className="w-3.5 h-3.5" /> PARKED
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Card 2: Main Dynamic Content */}
        <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl space-y-5">
          
          {/* STATE 1: PARKED */}
          {status === 'parked' && (
            <div className="space-y-5">
              <div className="flex items-center justify-between bg-slate-950 p-4 rounded-xl border border-slate-800">
                <div className="flex items-center gap-3">
                  <div className="bg-blue-500/10 p-2.5 rounded-lg text-blue-400">
                    <Clock className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">ระยะเวลาเข้าจอด</p>
                    <p className="text-sm font-semibold text-slate-100 font-mono">{formatDuration(parkedSeconds)}</p>
                  </div>
                </div>
                <div className="text-right">
                  <button 
                    onClick={() => setShowBreakdown(!showBreakdown)}
                    className="text-xs text-amber-400 underline font-medium flex items-center gap-1 justify-end"
                  >
                    <HelpCircle className="w-3.5 h-3.5" /> รายละเอียดค่าจอด
                  </button>
                  <p className="text-xs text-slate-400 mt-1">฿20 / ชั่วโมง</p>
                </div>
              </div>

              {/* Fee Breakdown Drawer */}
              {showBreakdown && (
                <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 text-xs space-y-1.5 font-mono text-slate-300">
                  <div className="flex justify-between"><span>เวลาเข้าจอด:</span><span>14:00 น.</span></div>
                  <div className="flex justify-between"><span>คำนวณเวลา:</span><span>{hoursParked} ชม. (ปัดเศษขึ้น)</span></div>
                  <div className="flex justify-between"><span>อัตราต่อชั่วโมง:</span><span>฿20.00</span></div>
                  <div className="flex justify-between text-amber-400 font-bold pt-1 border-t border-slate-800">
                    <span>รวมทั้งสิ้น:</span><span>฿{amount}.00</span>
                  </div>
                </div>
              )}

              {/* ALPR Snapshot Preview */}
              <div className="bg-slate-950 rounded-xl p-3 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                  <span className="flex items-center gap-1"><Camera className="w-3.5 h-3.5 text-blue-400" /> ภาพถ่ายบันทึกขาเข้า (ALPR)</span>
                  <span className="text-[10px] text-emerald-400 font-mono">MATCHED 98%</span>
                </div>
                <div className="relative h-28 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-center">
                  <div className="text-center space-y-1 z-20">
                    <Car className="w-7 h-7 text-slate-600 mx-auto" />
                    <p className="text-[11px] text-slate-400 font-mono">ENTRY LOG #{uid.slice(0, 4)}</p>
                  </div>
                  <span className="absolute bottom-2 left-2 text-[10px] bg-slate-950/90 text-amber-400 font-mono px-2 py-0.5 rounded border border-amber-400/30">
                    {licensePlate} | PASSED
                  </span>
                </div>
              </div>

              {/* Payment Action Bar */}
              <div className="flex justify-between items-center bg-amber-400/5 p-4 rounded-xl border border-amber-400/20">
                <div>
                  <span className="text-xs text-slate-400 block">ยอดชำระปัจจุบัน</span>
                  <span className="text-2xl font-extrabold text-amber-400 font-mono">฿{amount}.00</span>
                </div>
                <button
                  onClick={() => setStatus('paying')}
                  className="bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold px-5 py-2.5 rounded-xl transition text-sm flex items-center gap-2 shadow-lg shadow-amber-400/10"
                >
                  ชำระเงิน <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* STATE 2: PAYING (Mobile QR & Copy Code) */}
          {status === 'paying' && (
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 w-full flex justify-between items-center">
                <div className="text-left">
                  <p className="text-xs text-slate-400">สแกนชำระเงิน</p>
                  <p className="text-xl font-bold text-amber-400 font-mono">฿{amount}.00</p>
                </div>
                <div className="bg-blue-500/10 text-blue-400 px-3 py-1 rounded-full text-xs font-semibold">
                  PromptPay QR
                </div>
              </div>

              <div className="bg-white p-4 rounded-2xl shadow-2xl border-4 border-amber-400/20">
                <QRCodeSVG 
                  value={`00020101021229370016A000000677010111031500000000000005802TH5303764540${amount}.005802TH6304`} 
                  size={170} 
                />
              </div>

              <button 
                onClick={handleCopyPromptPay}
                className="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs py-2.5 rounded-xl border border-slate-700 flex items-center justify-center gap-1.5 transition"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {copied ? "คัดลอกข้อความจ่ายสำเร็จ!" : "คัดลอกข้อความจ่าย (สำหรับเปิดในแอปธนาคาร)"}
              </button>

              <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-400/10 px-4 py-2 rounded-lg border border-amber-400/20">
                <Clock className="w-4 h-4 animate-spin" />
                <span>ทำรายการภายใน: <strong className="font-mono">{formatClock(payCountdown)}</strong></span>
              </div>

              <div className="w-full pt-2 space-y-2">
                <button
                  onClick={() => setStatus('success')}
                  className="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-3 rounded-xl transition text-sm flex items-center justify-center gap-2"
                >
                  <CreditCard className="w-4 h-4" /> [จำลอง] กดเพื่อชำระเงินสำเร็จ
                </button>
                <button
                  onClick={() => setStatus('parked')}
                  className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-2 rounded-lg transition"
                >
                  ยกเลิก / กลับหน้าเดิม
                </button>
              </div>
            </div>
          )}

          {/* STATE 3: SUCCESS (Solving Exit Traffic Queue Pain Point) */}
          {status === 'success' && (
            <div className="flex flex-col items-center text-center py-2 space-y-4">
              <div className="w-14 h-14 bg-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center border border-emerald-500/30">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-emerald-400">ชำระเงินสำเร็จแล้ว!</h2>
                <p className="text-xs text-slate-300 mt-0.5">นำบัตร NFC ไปแตะออกที่หัวอ่าน PN532 ได้เลย</p>
              </div>

              {/* Grace Period Countdown & Extension Option */}
              <div className="w-full bg-slate-950 p-4 rounded-xl border border-amber-400/30 space-y-2">
                <span className="text-xs text-slate-400 block">เวลาที่เหลือในการนำรถออก (Grace Period)</span>
                <div className="text-3xl font-extrabold text-amber-400 font-mono">
                  {formatClock(exitCountdown)}
                </div>
                
                {/* Traffic Extension Button */}
                <button
                  onClick={handleExtendGracePeriod}
                  disabled={extendedTime}
                  className={`w-full text-xs py-2 rounded-lg border transition flex items-center justify-center gap-1.5 ${
                    extendedTime 
                      ? 'bg-slate-800 text-slate-500 border-slate-700' 
                      : 'bg-amber-400/10 text-amber-300 border-amber-400/30 hover:bg-amber-400/20'
                  }`}
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  {extendedTime ? "ขยายเวลาสำเร็จ (+5 นาทีเรียบร้อยแล้ว)" : "รถติดหน้าทางออก? กดเพิ่มเวลา +5 นาทีฟรี"}
                </button>
              </div>

              <div className="w-full bg-slate-950 p-3.5 rounded-xl border border-slate-800 text-left text-xs space-y-2">
                <div className="flex justify-between text-slate-400">
                  <span>รหัสบัตร NFC:</span>
                  <span className="font-mono text-amber-400 font-bold">{uid}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>ยอดชำระแล้ว:</span>
                  <span className="text-slate-100 font-bold">฿{amount}.00</span>
                </div>
              </div>

              <button
                onClick={() => setStatus('receipt')}
                className="w-full bg-slate-800 hover:bg-slate-700 text-amber-400 font-semibold py-2.5 rounded-xl text-xs flex items-center justify-center gap-2 border border-amber-400/30"
              >
                <Receipt className="w-4 h-4" /> ดูใบเสร็จรับเงิน (E-Receipt)
              </button>
            </div>
          )}

          {/* STATE 4: E-RECEIPT */}
          {status === 'receipt' && (
            <div className="space-y-4 text-left">
              <div className="bg-slate-950 p-5 rounded-xl border border-slate-800 space-y-3 font-mono text-xs">
                <div className="text-center pb-3 border-b border-slate-800">
                  <h3 className="text-sm font-bold text-amber-400">E-RECEIPT / ใบเสร็จรับเงิน</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">SMART PARKING MANAGEMENT SYSTEM</p>
                </div>
                <div className="space-y-1 text-slate-300">
                  <div className="flex justify-between"><span>RECEIPT NO:</span><span className="text-slate-100">#REC-{uid.slice(0, 4)}</span></div>
                  <div className="flex justify-between"><span>LICENSE PLATE:</span><span className="text-slate-100">{licensePlate}</span></div>
                  <div className="flex justify-between"><span>DURATION:</span><span className="text-slate-100">{hoursParked} ชั่วโมง</span></div>
                  <div className="flex justify-between"><span>PAYMENT METHOD:</span><span className="text-slate-100">PROMPTPAY</span></div>
                </div>
                <div className="pt-3 border-t border-slate-800 flex justify-between text-sm font-bold text-amber-400">
                  <span>TOTAL PAID:</span>
                  <span>฿{amount}.00</span>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => alert("ระบบดาวน์โหลดใบเสร็จรับเงินเรียบร้อยแล้ว")}
                  className="flex-1 bg-amber-400 text-slate-950 font-bold py-2.5 rounded-xl text-xs flex items-center justify-center gap-1.5"
                >
                  <Download className="w-4 h-4" /> ดาวน์โหลด PDF
                </button>
                <button
                  onClick={() => setStatus('success')}
                  className="bg-slate-800 text-slate-300 py-2.5 px-4 rounded-xl text-xs"
                >
                  ย้อนกลับ
                </button>
              </div>
            </div>
          )}

          {/* STATE 5: SOS / HARDWARE FAILURE OVERRIDE */}
          {status === 'sos' && (
            <div className="space-y-4 text-center py-2">
              <div className="w-12 h-12 bg-rose-500/20 text-rose-400 rounded-full flex items-center justify-center mx-auto border border-rose-500/30">
                <PhoneCall className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <h3 className="text-base font-bold text-rose-400">ขอความช่วยเหลือ / รหัสผ่านทางฉุกเฉิน</h3>
                <p className="text-xs text-slate-400 mt-1">กรณีแตะบัตร NFC แล้วไม้กั้นไม่เปิด หรือเครื่องอ่านมีปัญหา</p>
              </div>

              {/* Emergency Pass Display */}
              <div className="bg-slate-950 p-4 rounded-xl border border-rose-500/30 space-y-3">
                <p className="text-xs text-slate-300">แสดง QR ฉุกเฉินนี้แก่ รปภ. หรือกล้องสแกนเพื่อเปิดไม้กั้น:</p>
                <div className="bg-white p-3 rounded-lg w-fit mx-auto">
                  <QRCodeSVG value={`EMERGENCY-PASS-${uid}`} size={130} />
                </div>
                <p className="text-[11px] font-mono text-amber-400">PASS CODE: OVERRIDE-{uid}</p>
              </div>

              <button
                onClick={() => setStatus('parked')}
                className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 py-2.5 rounded-xl text-xs"
              >
                ย้อนกลับสู่หน้าหลัก
              </button>
            </div>
          )}

        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <button className="bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 py-2.5 rounded-xl flex items-center justify-center gap-2 transition">
            <History className="w-3.5 h-3.5" /> ประวัติการแตะบัตร
          </button>
          <button className="bg-slate-900 hover:bg-slate-800 border border-slate-800 text-rose-400/80 py-2.5 rounded-xl flex items-center justify-center gap-2 transition">
            <Lock className="w-3.5 h-3.5" /> อายัดบัตร NFC
          </button>
        </div>

      </div>
    </div>
  );
}

export default function PaymentPage() {
  return (
    <Suspense fallback={null}>
      <PaymentContent />
    </Suspense>
  );
}