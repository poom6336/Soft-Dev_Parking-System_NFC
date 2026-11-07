'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import mqtt from 'mqtt';
import { Car, Search, QrCode, Sparkles, AlertCircle, Loader2 } from 'lucide-react';

export default function SearchPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [mqttClient, setMqttClient] = useState<mqtt.MqttClient | null>(null);

  // เชื่อมต่อ MQTT Broker
  useEffect(() => {
    const client = mqtt.connect('wss://broker.emqx.io:8084/mqtt');
    setMqttClient(client);

    return () => {
      client.end();
    };
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm.trim()) {
      setErrorMsg('กรุณากรอกเลขทะเบียนรถ');
      return;
    }

    if (!mqttClient) {
      setErrorMsg('ระบบเครือข่ายยังไม่พร้อม กรุณาลองใหม่อีกครั้ง');
      return;
    }

    setLoading(true);
    setErrorMsg('');

    const requestId = `req_${Date.now()}`;
    const responseTopic = `parking/search/response/${requestId}`;

    // Subscribe รอรับคำตอบจาก Python Edge Node
    mqttClient.subscribe(responseTopic, () => {
      mqttClient.publish(
        'parking/search/request',
        JSON.stringify({
          query: searchTerm.trim(),
          requestId: requestId,
        })
      );
    });

    // รับข้อมูลตอบกลับจาก Python
    const handleMessage = (topic: string, message: Buffer) => {
      if (topic === responseTopic) {
        try {
          const data = JSON.parse(message.toString());
          mqttClient.unsubscribe(responseTopic);
          mqttClient.removeListener('message', handleMessage);

          if (data.found && data.uid) {
            // ค้นหาเจอ -> Redirect ไปยังหน้าชำระเงิน (/pay?uid=...&plate=...)
            router.push(`/pay?uid=${encodeURIComponent(data.uid)}&plate=${encodeURIComponent(data.plate)}`);
          } else {
            setLoading(false);
            setErrorMsg(data.message || 'ไม่พบข้อมูลการจอดรถของทะเบียนนี้ในปัจจุบัน');
          }
        } catch {
          setLoading(false);
          setErrorMsg('เกิดข้อผิดพลาดในการอ่านข้อมูล');
        }
      }
    };

    mqttClient.on('message', handleMessage);

    // Timeout เผื่อ Python ไม่ตอบกลับภายใน 5 วินาที
    setTimeout(() => {
      mqttClient.unsubscribe(responseTopic);
      mqttClient.removeListener('message', handleMessage);
      setLoading((prev) => {
        if (prev) setErrorMsg('ไม่สามารถเชื่อมต่อฐานข้อมูลลานจอดรถได้ (Timeout)');
        return false;
      });
    }, 5000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-center items-center p-4 font-sans relative overflow-hidden">
      {/* Background Blur */}
      <div className="absolute -top-32 -left-32 w-80 h-80 bg-blue-600/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-80 h-80 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />

      <main className="w-full max-w-md bg-slate-900/90 border border-slate-800 backdrop-blur-md rounded-3xl p-6 sm:p-8 shadow-2xl relative z-10 space-y-6">
        {/* Header Icon */}
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="w-16 h-16 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-2xl flex items-center justify-center shadow-inner">
            <Car className="w-9 h-9" />
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
            SMART PARKING <Sparkles className="w-5 h-5 text-amber-400 fill-amber-400" />
          </h1>
          <p className="text-xs text-slate-400">
            ระบบค้นหาข้อมูลการจอดรถและชำระเงินอัตโนมัติ
          </p>
        </div>

        {/* Search Form */}
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300 block">
              กรอกทะเบียนรถ หรือ เลขท้ายทะเบียน
            </label>
            <div className="relative">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="เช่น กท-1234 หรือ 1234"
                className="w-full bg-slate-950 border border-slate-700 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 text-slate-100 text-lg font-bold rounded-2xl px-4 py-3.5 pl-11 outline-none transition-all placeholder:font-normal placeholder:text-slate-600 uppercase"
              />
              <Search className="w-5 h-5 text-slate-500 absolute left-4 top-1/2 -translate-y-1/2" />
            </div>
          </div>

          {errorMsg && (
            <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-bold py-3.5 px-4 rounded-2xl transition-all shadow-lg shadow-blue-600/25 flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>กำลังค้นหาข้อมูล...</span>
              </>
            ) : (
              <>
                <Search className="w-5 h-5" />
                <span>ค้นหาข้อมูลการจอดรถ</span>
              </>
            )}
          </button>
        </form>

        {/* Info Footer */}
        <div className="border-t border-slate-800/80 pt-4 text-center space-y-2">
          <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
            <QrCode className="w-4 h-4 text-slate-500" />
            <span>สแกน QR Code เพื่อเข้าหน้านี้ได้ทุกเสาในลานจอดรถ</span>
          </div>
        </div>
      </main>

      <footer className="mt-8 text-xs text-slate-600 text-center">
        Smart Parking System © 2026 — CPR.E KMUTNB
      </footer>
    </div>
  );
}