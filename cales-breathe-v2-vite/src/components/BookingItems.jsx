const BookingItems = [

      {
        category: "臉部",
        description: "4選1",
        items: [
            { id: "face-eyebrow", name: "眉毛", price: 600, duration: 30 },
            { id: "face-lip", name: "上唇", price: 400, duration: 15 },
            { id: "face-eyebrow-lip",name: "眉毛 + 上唇", price: 1000, duration: 45 },
            { id: "face-full", name: "全臉", price: 1600, duration: 60 },
        ],
      },
      {
        category: "私密處",
        description: "5選1",
        items: [
            { id: "intimate-vio", name: "巴西式全除VIO", price: 2200, duration: 40 ,allowAddons: true},
            { id: "intimate-vio-mask", name: "巴西式全除VIO + 敷膜", price: 2599, duration: 55 ,allowAddons: true},
            { id: "intimate-bikini", name: "比基尼線", price: 2000, duration: 20 ,allowAddons: true},
            { id: "intimate-bikini-mask", name: "比基尼線 + 敷膜", price: 2399, duration: 35 ,allowAddons: true},
            { id: "intimate-package", name: "質感在身邊", price: 2800, duration: 90 ,allowAddons: true},
        ],
      },
      {
        category: "手臂",
        description: "4選1",
        items: [
            { id: "arms-armpit", name: "腋下", price: 700, duration: 15 },
            { id: "arms-forearms", name: "前手臂", price: 1000, duration: 40 },
            { id: "arms-armpit-forearms", name: "腋下 + 前手臂", price: 1700, duration: 45 },
            { id: "arms-full", name: "全手", price: 1800, duration: 60 ,allowAddons: true},       
        ],
      },
      {
        category: "胸部",
        description: "2選1",
        items: [
            { id: "chest-full", name: "胸部", price: 900, duration: 30 },
            { id: "chest-nipples", name: "乳暈", price: 600, duration: 15 },      
        ],
      },
      {
        category: "腿部",
        description: "2選1",
        items: [
            { id: "legs-cuff", name: "小腿", price: 1500, duration: 30 },
            { id: "legs-full", name: "全腿", price: 2500, duration: 60, allowAddons: true},
        ],
      },
      {
        category: "背部",
        description: "",
        items: [
            { id: "back", name: "背部除毛", price: 1500, duration: 40 },
        ],
      },
      {
        category: "腹部", 
        description: "",
        items: [
            { id: "belly", name: "腹部除毛", price: 1000, duration: 30 },
        ],
      },
      {
        category: "臀部",
        description: "",
        items: [
            { id: "butt", name: "臀部除毛", price: 900, duration: 30 },
        ],
      },
      {
        category: "手指",
        description: "",
        items: [
            { id: "fingers", name: "手指除毛", price: 400, duration: 10 },
        ],
      },
      {
        category: "腳趾",
        description: "",
        items: [
            { id: "toes", name: "腳趾除毛", price: 400, duration: 10 },
        ],
      },    
]

export default BookingItems;