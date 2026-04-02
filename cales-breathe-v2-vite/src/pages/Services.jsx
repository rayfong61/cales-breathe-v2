import WaxingPackages from '../components/WaxingPackages';
import WaxingServices from '../components/WaxingServices';
import { Link } from "react-router-dom";

 

function Services() {
  return (
    <div>
    <section
          id="waxServices"
          className="relative max-w-full mx-auto p-4 flex flex-col justify-center text-center items-center min-h-80 overflow-hidden">
          {/* 背景圖層 */}
          <div className="absolute inset-0 bg-[url('/waxServices.jpg')] bg-cover bg-center z-0" />

          {/* 前景內容 */}
          <div className="relative z-10 ">
            <h2 className="text-7xl sm:text-8xl text-white text-shadow-xs leckerli-one-regular">
              Wax Services
            </h2>
           
            
          </div>
        </section>
    <section className="py-16 px-14 ">
      <div className="max-w-5xl mx-auto space-y-20">
        {WaxingServices.map((section) => (
          <div key={section.category}>
            
            <div className="grid md:grid-cols-2 gap-x-5 mb-10">
              
              
              <div>
                <h2 className="text-rose-300 text-4xl/14 font-bold mb-5 sm:text-5xl/18">{section.category}</h2>
                <p className="sm:text-xl mb-6">{section.description}</p>
              </div>
              <img src={section.imgSrc} alt="WaxingItem" className='w-full h-full object-cover rounded-4xl' />

              
            </div>
            



            <ul className="grid sm:grid-cols-2 md:grid-cols-3 gap-x-10 ">
              {section.items.map((item) => (
                <li key={item.name} className="flex justify-between items-start py-3 border-b">
                  <div>
                    <h3 className="text-base sm:text-lg font-semibold">{item.name}</h3>
                    <p className="text-xs sm:text-sm">{item.desc} 分鐘</p>
                  </div>
                  <span className="text-base sm:text-lg font-bold">{item.price}</span>
                </li>
              ))}
            </ul>
            <Link to="/booking">
                <button className="rounded-full px-20 py-2 mt-10 text-lg md:text-xl hover:opacity-80  cursor-pointer bg-pink-600 text-white block mx-auto font-sans">
                            BOOK NOW
                </button>
            </Link>
          </div>
        ))}
      </div>
      <div className="max-w-5xl mx-auto space-y-12 py-20">
        {WaxingPackages.map((section) => (
          <div key={section.category}>
            <div className="grid md:grid-cols-2 gap-x-10 mb-10">
            <div>
            <h2 className="text-rose-400 text-4xl/14 font-bold mb-5 sm:text-5xl/18">{section.category}</h2>
            <p className="sm:text-xl mb-6">{section.description}</p>
            </div>
            <img src="package.png" alt="facial_waxing" className='w-full h-full object-cover rounded-4xl' />
            </div>
            <ul>
              {section.items.map((item) => (
                <li key={item.name} className="flex justify-between gap-16 items-start py-3 border-b">
                  <div>
                    <h3 className="text-base sm:text-lg font-semibold">{item.name}</h3>
                    <p className="text-xs sm:text-sm">{item.desc} 分鐘</p>
                  </div>
                  <span className="text-base sm:text-lg font-bold">{item.price}</span>
                </li>
              ))}
            </ul>
            <Link to="/booking">
                <button className="rounded-full px-20 py-2 mt-10 text-lg md:text-xl hover:opacity-80  cursor-pointer bg-pink-600 text-white block mx-auto font-sans ">
                            BOOK NOW
                </button>
            </Link>
            
          </div>
        ))}
      </div>     
      
                
      
    </section>
                        
    </div>
  );
}

export default Services;