I need to make a python project that can optimize the output based on the TOU rate plan cost and do the modification in the incoming raw data. 


Input - 


1. Rate defination and appliance level data


INPUT - 

{
  "metadata": {
    "granularity": 3600,
    "startTime": 1709251200,
    "totalTimeSlots": 744,
    "timezone": "Asia/Kolkata"
  },

  "rates": {
    "rateVector": [3.5, 3.5, 3.5, ..., 8.5, ..., 6.0] // every hour rate for a bill cycle 
  },

  "tou": {
    "mapping": [
      { "type": "offPeak", "startHour": 0, "endHour": 15 },
      { "type": "onPeak", "startHour": 15, "endHour": 22 },
      { "type": "midPeak", "startHour": 22, "endHour": 24 }
    ],
    "rates": {
      "offPeak": 3.5,
      "midPeak": 6.0,
      "onPeak": 8.5
    }
  },

  "appliances": [
    {
      "appId": 71,
      "name": "AC",
      "shiftable": true,
      "blocks": [
        {
          "blockId": 1,
          "start_t": 17,
          "duration": 3,
          "consumption": [1.2, 1.5, 1.3],
          "constraints": {
            "maxShiftHours": 2,
            "allowedWindows": [
              { "startHour": 12, "endHour": 18 }
            ]
          }
        }
      ]
    },
    {
      "appId": 72,
      "name": "Fridge",
      "shiftable": false,
      "blocks": [
        {
          "blockId": 1,
          "start_t": 0,
          "duration": 744,
          "consumption": [0.2, 0.2, 0.2, ...]
        }
      ]
    }
  ]
}

2. OUTPUT - 


{
  "metadata": {
    "granularity": 3600,
    "totalTimeSlots": 744,
    "currency": "INR"
  },
  "loadShift": [
    {
      "appId": 71,
      "totalSavings": 13.1,
      "blockShifts": [
        {
          "blockId": 1,
          "originalStart_t": 17,
          "newStart_t": 14,
          "duration": 3,
          "consumption": [1.2, 1.5, 1.3],
          "costBefore": 45.2,
          "costAfter": 32.1,
          "savings": 13.1
        }
      ]
    }
  ]
}



Now I want to build a MILP algo that will take my rates + tou + appliances as input through an API call 

and shift appliance contiguous block wise to get the lowest rate it can within a single day and give me the OUTPUT in the above structure. Only if shiftable is true 


