import { Link } from 'react-router-dom';
import Testimonial from "../components/Testimonial";

function Home() {
    return (
      <div>


      <section
        id="hero"
        className="relative max-w-full mx-auto p-4 flex flex-col justify-center text-center items-center min-h-dvh overflow-hidden"
      >
        {/* 背景影片層 */}
        <video
          className="absolute inset-0 w-full h-dvh object-cover z-0"
          autoPlay
          muted
          loop
          playsInline
        >
          <source src="https://pub-cdd09c31cc514fd89032dc45ed4a34ee.r2.dev/others/hero14.mp4" type="video/mp4" />
          您的瀏覽器不支援影片播放。
        </video>

        {/* 前景內容 */}
        <div className="relative z-10">
          <h2 className=" text-rose-400 text-shadow-lg text-[clamp(2rem,5vw,3rem)]">
            質 感 香 氣 / 熱 蠟 美 肌
          </h2>
          <h1 className=" py-6 text-[clamp(1rem,5vw,2rem)] text-white text-shadow-lg">
            讓 肌 膚 深 呼 吸，讓 妳 自 在 閃 耀
          </h1>
          <Link to="/services">
            <button className="rounded px-12 py-3 mt-20 text-lg hover:opacity-80 md:text-xl cursor-pointer bg-rose-400 text-white">
              服務項目
            </button>
          </Link>
        </div>
      </section>

      <section id="specials" className='max-w-full mx-auto py-10 bg-gray-50  text-xl sm:text-2xl'>
        <h1 className="text-5xl sm:text-6xl text-center my-6 text-pink-300 leckerli-one-regular flex justify-center items-center gap-4">
           Cale's specials  
        </h1>
        <div className='max-w-5xl mx-auto px-5  grid grid-cols-2 md:grid-cols-3'>
          <div className='py-10 flex justify-center items-center '>
            <img src="005-mother.png" className="h-12"></img>
            孕婦除毛專門 
          </div>
          <div className='py-10 flex justify-center items-center '>
            <img src="006-bikini.png" className="h-12"></img>
            巴西式全除專門 
          </div>
          <div className='py-10 flex justify-center items-center '>
            <img src="waxing.png" className="h-12 mr-1"></img>
            RICA熱蠟品牌
          </div>
          
          <div className='py-10 flex justify-center items-center '>
            <img src="aromatherapy.png" className="h-11"></img>
            芳香療法
          </div>
          <div className='py-10 flex justify-center items-center '>
            <img src="008-trash-can.png" className="h-10 mr-2"></img>
            拋棄式耗材
          </div>
          <div className='py-10 flex justify-center items-center '>
            <img src="012-smiling-baby.png" className="h-10 mr-2"></img>
            親子友善
          </div>
        </div>
        

      </section>


      <section id="story" className='max-w-5xl mx-auto px-15 py-20 grid sm:grid-cols-2 gap-x-10'>
        
        <div className='flex flex-col justify-center items-center'>
        <h2 className="text-3xl/10 md:text-4xl/12 mb-6 text-shadow-lg">
        使 用 芳 香 療 法 融 合 熱 蠟 美 肌 ，呵 護 您 的 肌 膚
        </h2>
        <article className="text-base/8 md:text-lg/10 text-shadow-md mb-10">
            <p >
              希臘神話的眾女神中, 有一位女神叫<span className='font-bold'>Cale</span>,
              音：「卡蕾～」,代表優雅、美麗、有魅力的女人的意思,
              在Cale's Breathe的空間裡, 我們運用芳香療法結合熱蠟除毛🌿,
              在這個空間裡, 妳聞的香氣都是天然精油和植物熱蠟的味道,  香香的。
            </p>
            <p >
              做完熱蠟美肌後🍯, 從臉到腳的每個毛孔都純淨的在呼吸, 
              像嬰兒的呼吸般純淨, 帶著甜蜜的輕喘, 綻放心心點點的美麗。
            </p>
        </article>
        </div>
        <img src="001.jpg" className='w-full h-full rounded-t-full object-cover'></img>
      </section>
      {/* <div id="services" className='pt-16'><Services /></div> */}
      
      <Testimonial />
        </div>
        
    );
  }
  
  export default Home;
  