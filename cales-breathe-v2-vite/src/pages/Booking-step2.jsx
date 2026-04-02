import React, { useState, useEffect } from "react";
import { useLocation, BrowserRouter as Router } from "react-router-dom";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { Link } from 'react-router-dom';
import AddingItems from "../components/AddingItems";
import { addMonths } from "date-fns";


// 手動設定不可預約日期
const offDates = ["2025-06-20","2025-06-28","2025-07-04", "2025-07-05"];

// const unavailableTimes = {
//   "2025-05-04": ["10:00", "14:00"],
//   "2025-05-03": ["10:00", "14:00"]
// };

const allTimeSlots = [
  "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"
];

const formatDate = (date) => {
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0"); 
  //d.getMonth() 會回傳「0 到 11」的值（0 表示一月，11 表示十二月）。
  //用 String(...).padStart(2, "0") 是為了補 0，比如 5 會變成 "05"，確保兩位數格式。
  
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

function BookingDateTimeContent() {
  const api = import.meta.env.VITE_API_BASE;
  const location = useLocation();
  const [selectedServices, setSelectedServices] = useState([]);
  const [selectedAddons, setSelectedAddons] = useState([]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedTime, setSelectedTime] = useState("");
  const [confirmedBooking, setConfirmedBooking] = useState(null);
  const [total, setTotal] = useState(0);
  const [totalDuration, setTotalDuration] = useState(0);
  const [unavailableDates, setUnavailableDates] = useState([]);  // 預約「已滿」日期

  useEffect(() => {
    fetch(`${api}/unavailable-dates`) // 找出預約「已滿」日期
      .then((res) => res.json())
      .then((data) => setUnavailableDates(data))
      .catch((err) => console.error("Failed to load unavailable dates", err));
  }, []);

  // console.log(unavailableDates);

  

  useEffect(() => {
    const stored = localStorage.getItem("bookingData");
    if (stored) {
      const parsed = JSON.parse(stored);
      setSelectedServices(parsed.selectedServices || []);
      setSelectedAddons(parsed.selectedAddons || []);
      setTotal(parsed.total || []);
      setTotalDuration(parsed.totalDuration || []);
    }
  }, []);

  const isDateAvailable = (date) => {
    const dateStr = formatDate(date);
    const isSunday = date.getDay() === 0; // Sunday = 0
    const isWednesday = date.getDay() === 3; // 
    return !isWednesday && !isSunday && !offDates.includes(dateStr) && !unavailableDates.includes(dateStr);  
      // 「這天不是星期三，也不是星期日，也不在公休日和客滿日中 → 就允許選擇這一天。」
  };

  // const getAvailableTimes = () => {
  //   if (!selectedDate) return [];
  //   const dateStr = formatDate(selectedDate);
  //   const timesUnavailable = unavailableTimes[dateStr] || [];
  //   return allTimeSlots.filter((time) => !timesUnavailable.includes(time));
  // };

  //  時間重疊判斷邏輯（JS）
  const isTimeSlotUnavailable = (slotTime, bookings) => {
    const slotStart = new Date(`1970-01-01T${slotTime}:00`);
    const slotEnd = new Date(slotStart.getTime() + 60 * 60 * 1000); // 1 小時 slot
  
    return bookings.some(({ start_time, end_time }) => {
      const bookedStart = new Date(`1970-01-01T${start_time}`);
      const bookedEnd = new Date(`1970-01-01T${end_time}`);
      return slotStart < bookedEnd && slotEnd > bookedStart; // 重疊
    });
  };

  const [unavailableTimeRanges, setUnavailableTimeRanges] = useState([]);

  useEffect(() => {
    if (!selectedDate) return;
    const dateStr = formatDate(selectedDate);

    fetch(`${api}/unavailable-times?date=${dateStr}`)
      .then(res => res.json())
      .then(data => setUnavailableTimeRanges(data))
      .catch(err => console.error(err));
  }, [selectedDate]);

const getAvailableTimes = () => {
  if (!selectedDate) return [];
  return allTimeSlots.filter((time) => !isTimeSlotUnavailable(time, unavailableTimeRanges));
};




  const handleConfirm = () => {
    const bookingDetails = {
      ...JSON.parse(localStorage.getItem("bookingData")),
      date: formatDate(selectedDate),
      time: selectedTime,
    };
    localStorage.setItem("bookingData", JSON.stringify(bookingDetails));
    setConfirmedBooking(bookingDetails);
    // console.log(bookingDetails);
  };

  return (
    <div className="max-w-xl mx-auto p-6 my-6 bg-white rounded-xl shadow-md">
      
      <h2 className="text-xl font-bold mb-4">選擇預約日期與時間</h2>

      <div className="mb-4">
        <label className="block mb-1 font-semibold">選擇日期：</label>
        <DatePicker
          selected={selectedDate} // 綁定目前選擇的日期狀態（selectedDate）, 讓元件是「受控元件」（controlled component）。
          onChange={(date) => {
            setSelectedDate(date);
            setSelectedTime("");
            setConfirmedBooking(null);
          }}
          filterDate={isDateAvailable}
          minDate={new Date()} // 限制最早可以選擇「今天」，不能選過去的日期。
          maxDate={addMonths(new Date(), 2)} // 限制最晚可選擇兩個月後的日期
          dateFormat="yyyy-MM-dd" // 設定輸出的日期格式為 年-月-日，例如：2025-05-07。
          className="border p-2 w-full"
        />
      </div>

      {selectedDate && (
        <div className="mb-4">
          <label className="block mb-1 font-semibold">可預約時段：</label>
          <div className="grid grid-cols-3 gap-2">
            {getAvailableTimes().map((time) => (
              <button
              key={time}
              // disabled={isTimeSlotUnavailable(time, unavailableTimeRanges)}
              onClick={() => setSelectedTime(time)}
              className={`border p-2 rounded text-center cursor-pointer
                ${
                  // isTimeSlotUnavailable(time, unavailableTimeRanges)
                  // ? "bg-gray-300 text-gray-500 cursor-not-allowed" :
                      selectedTime === time
                    ? "bg-rose-500 text-white"
                    : "bg-white hover:bg-gray-100"
                }`}
            >
              {time}
            </button>
            ))}
          </div>
        </div>
      )}
      {(selectedServices.length > 0 || selectedAddons.length > 0) && (
        <div className="m-3 p-4 text-md border-l-4  border-rose-400 text-gray-700">
          <p className="font-semibold mb-1">已選擇的項目：</p>
          <ul className="list-disc ml-5">
            {selectedServices.map((item) => (
              <li key={item.id}>{item.name} - ${item.price}</li>
            ))}
            {selectedAddons.map((id) => {
             const addon = AddingItems.find((item) => item.id === id);
            return (
              <li key={id}>
                加購項目：{addon?.name} - ${addon?.price}
              </li>
            );
          })}
          </ul>
          <br />
          總時間: {totalDuration} 分鐘
         <br />
          總金額: {total} 元
        </div>
      )}

      {selectedDate && selectedTime && (
        <div className="mt-4 text-lg font-semibold">
          選擇時間：{formatDate(selectedDate)} {selectedTime}
        </div>
      )}

      <div className="mt-6 flex justify-between">
        <Link to="/booking">
          <button className="bg-rose-200  hover:bg-rose-300 px-4 py-2 rounded w-30 cursor-pointer">上一步</button>
        </Link>
        
        <Link to="/booking-step3">
          <button
            className="bg-rose-500 hover:bg-rose-600 text-white px-4 py-2 rounded  w-30 disabled:opacity-50 cursor-pointer"
            disabled={!selectedDate || !selectedTime}
            onClick={handleConfirm}
          >
            下一步
          </button>
       </Link>
      </div>

      

     

      
    </div>
  );
}

export default BookingDateTimeContent;
