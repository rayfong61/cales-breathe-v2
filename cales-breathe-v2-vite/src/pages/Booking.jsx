import React, { useState }  from 'react'
import BookingItems from '../components/BookingItems';
import AddingItems from '../components/AddingItems';
import { Link } from "react-router-dom";

function Booking() {
  const [selectedItemIds, setSelectedItemIds] = useState({});
  const [selectedAddons, setSelectedAddons] = useState([]);

  // 根據使用者目前點的選項，去更新該分類的選取狀態，並保留其他分類原本的設定
  const handleSingleSelect = (category, itemId) => {
    setSelectedItemIds((prev) => ({
      ...prev,
      [category]: prev[category] === itemId ? null : itemId
    }));
  };
  // selectedItemIds會長這樣:
  // {
  //   "臉部": "face-eyebrow",
  //   "私密處": "intimate-vio"
  // }
  
  // 若選擇的項目先前已包含在陣列，則取消選取該項目再回傳，反向則保留先前項目並增加該項目
  const toggleAddon = (id) => {
    setSelectedAddons((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };


  // 根據目前使用者選的項目，找出那些選取的項目資料(用來決定是否加購)

  const getSelectedItems = () => {
    const selected = [];
    // 這裡宣告一個空陣列 selected，等等要把所有使用者選的項目資料 push 進去。

    for (const category of BookingItems) {
    //  loop 每個分類（例如：臉部、私密處、手臂……）

      const selectedId = selectedItemIds[category.category];
      // 這裡透過類別名稱（例如 "臉部"）去 selectedItemIds 找出使用者在這個類別下選的項目 id。

      if (selectedId) {
        const item = category.items.find((i) => i.id === selectedId);
        // 如果這個類別有選項被選了，就在該類別的 items 陣列中找到對應的 item。

        if (item) selected.push(item);
        // 如果真的有找到符合的項目，就把它放進 selected 陣列。
      }
    }
    return selected;

  // selected 會長這樣
  // [
  // { id: "face-full", name: "全臉", price: 1600, duration: 60 },
  // { id: "legs-full", name: "全腿", price: 2500, duration: 60 },
  //  ]
  };
  
  // 加購條件
  const canAddAddons = () => {
    const selected = getSelectedItems();
    return selected.some(
      (item) => 
        item.allowAddons  
        //  有些 item 自己就有 allowAddons: true 的屬性（可在資料中加上這個欄位）
        // || item.id === "legs-full" || 
        // item.id === "arms-full" || 
        // BookingItems.find(c => c.category === "私密處")?.items.some(i => i.id === item.id)
        // 如果目前這個項目是在「私密處」這個類別裡，會回傳 true；
        // 否則會回傳 false 或 undefined（但整體不會錯，因為有 ?. 保護）。
    );
  };

  // 計算目前使用者所選的 總金額（主項目 + 加購項目）
  const calculateTotal = () => {

    const serviceTotal = getSelectedItems().reduce((sum, item) => sum + item.price, 0);

    const addonTotal = canAddAddons()
      ? selectedAddons.reduce((sum, id) => {
            const addon = AddingItems.find((item) => item.id === id);
            return sum + (addon?.price || 0);
            // 如果找不到 addon，就用 0 避免報錯，確保 .reduce() 可以順利執行。
          }, 0)  
      : 0;
      // const addonTotal = canAddAddons() ? ... : 0
      // 如果目前的主項目允許加購項目（加購開關為 true），才去計算加購的總金額；否則就是 0。

    return serviceTotal + addonTotal;
  };

  // 計算目前使用者所選的 總時間（主項目 + 加購項目）
  const calculateDuration = () => {
    const serviceTime = getSelectedItems().reduce((sum, item) => sum + item.duration, 0);
    const addonTime = canAddAddons()
      ? selectedAddons.reduce((sum, id) => {
          const addon = AddingItems.find((item) => item.id === id);
          return sum + (addon?.duration || 0);
        }, 0)
      : 0;
    return serviceTime + addonTime;
  };

  // 重新選擇
  const resetSelections = () => {
    setSelectedItemIds({});
    setSelectedAddons([]);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // 下一頁功能
  const handleNext = () => {
    localStorage.setItem("bookingData", JSON.stringify({
      selectedServices: getSelectedItems(),
      selectedAddons,
      total: calculateTotal(),
      totalDuration: calculateDuration(),
    }));
  };

// test~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  //  console.log(selectedItemIds);
  //  console.log(selectedAddons);
  //  console.log(getSelectedItems());

  return (
    <div className="max-w-xl mx-auto p-6 my-6 bg-white rounded-xl shadow-md">
      <h1 className="text-2xl font-bold mb-4">Cale's Breathe 熱蠟除毛預約服務:</h1>
      {BookingItems.map((cat) => (
        <div key={cat.category} className="mb-6">
          <h2 className="text-xl font-semibold mb-2">
            {cat.category} {cat.description && `(${cat.description})`}
          </h2>
          {cat.items.map((item) => (
            <label key={item.id} className="block mb-1">
              <input
                type="checkbox"
                name={cat.category}
                checked={selectedItemIds[cat.category] === item.id}
                onChange={() => handleSingleSelect(cat.category, item.id)}
              />
              <span className="text-lg ml-2">
                {item.name} - ${item.price} - {item.duration}分鐘
              </span>
            </label>
          ))}
        </div>
      ))}

      {canAddAddons() && (
        <div className="mb-6">
          <h2 className="text-lg text-rose-400 font-semibold mb-2">加購項目</h2>
          <div className='ml-2 pl-2 border-l-3 border-rose-400'>
            {AddingItems.map((addon) => (
              <label key={addon.id} className="block mb-1 text-lg">
                <input
                  type="checkbox"
                  checked={selectedAddons.includes(addon.id)}
                  onChange={() => toggleAddon(addon.id)}
                />
                <span className="ml-2">
                  {addon.name} - ${addon.price} - {addon.duration}分鐘
                </span>
              </label>
            ))}
          </div>
        </div>
      )}
       
      <hr/>
      <div className="font-bold text-lg my-4">
        
        預約項目: 
        <ul className="list-disc list-inside font-normal text-rose-400 mt-2">
          {getSelectedItems().map((item)=>
          <li key={item.id}>
             {item.name} - ${item.price} - {item.duration}分鐘
          </li>
          )}

          {canAddAddons() &&
          selectedAddons.map((id) => {
          const addon = AddingItems.find((item) => item.id === id);
          return (
            <li key={id}>
              {addon.name} - ${addon.price} - {addon.duration}分鐘
            </li>
          );
          })}
        </ul>
        <br />
        總時間: {calculateDuration()} 分鐘
       <br />
        總金額: {calculateTotal()} 元
        
      </div>

        <div className="mt-6 flex justify-between">

        <button
        
        className="bg-rose-200 hover:bg-rose-300 px-4 py-2 rounded w-30 disabled:opacity-50 cursor-pointer"
        onClick={resetSelections}
      >
        重新選擇
      </button> 
      <Link to="/booking-step2">
        <button
          disabled={!getSelectedItems().length}
          className="bg-rose-500 hover:bg-rose-600 text-white px-4 py-2 rounded w-30 disabled:opacity-50 cursor-pointer"
          onClick={handleNext}
        >
          下一步
        </button> 
      </Link>

        </div>
       
    </div>
  );
}

export default Booking;
