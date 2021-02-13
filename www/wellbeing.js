/*
Wellbeing Water Well Monitor and Guard
David Sundstrom
2020
*/


function initialize() {

    let vh = window.innerHeight - 45;
    document.documentElement.style.setProperty('--vh', `${vh}px`);
    let vw = window.innerWidth;
    document.documentElement.style.setProperty('--vw', `${vw}px`);

    window.addEventListener('resize', () => {
      let vh = window.innerHeight - 45;
      let vw = window.innerWidth;
      document.documentElement.style.setProperty('--vh', `${vh}px`);
      document.documentElement.style.setProperty('--vw', `${vw}px`);
    });

    closeConfig(false);
    displayTime();
    setBoardTime();
    refresh();
    websocket();
}

function setBoardTime() {
    var today = new Date();
    var tuple = {
        year: today.getFullYear(),
        month: today.getMonth() + 1, // python is 1-12, javascript 0-11
        monthDay: today.getDate(),
        hour: today.getHours(),
        minute: today.getMinutes(),
        second: today.getSeconds(),
        weekday: (today.getDay() - 1) % 7 // python is Monday = 0, javascript is Sunday = 0
    }

    fetch("/api/setDateTime", {
        method: "POST",
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(tuple)
    })
}

function displayTime() {
    var today = new Date();

    var s = timeToString(today);
    document.getElementById("timevalue").innerHTML = s;

    s = dateToString(today);
    document.getElementById("datevalue").innerHTML = s;
    
    var time = setTimeout(function(){ displayTime() }, 500);
}

function dateToString(d) {
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'June', 'July', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'];
    var curDay = d.getDate();
    var curMonth = months[d.getMonth()];
    var curYear = d.getFullYear();
    var s = curDay+" "+curMonth+" "+curYear;
    return s
}

function timeToString(d) {
    var hr = d.getHours();
    var min = d.getMinutes();
    var sec = d.getSeconds();
    hr = (hr == 0) ? 12 : hr;
    hr = padTime(hr);
    min = padTime(min);
    sec = padTime(sec);
    return hr + ":" + min + ":" + sec;
}

function padTime(i) {
    if (i < 10) {
        i = "0" + i;
    }
    return i;
}

function updateStatus(status) {
    if (status == "ON") {
        document.getElementById('statusvalue').style.backgroundColor = "blue";
        document.getElementById('statusvalue').innerHTML = "ON";
        document.getElementById("stats").removeAttribute("fault");
    }
    else if (status == "FAULT") {
        document.getElementById('statusvalue').style.backgroundColor = "red";
        document.getElementById('statusvalue').innerHTML = "FAULT";
        document.getElementById("stats").setAttribute("fault",true);
    } else {
        document.getElementById('statusvalue').style.backgroundColor = "green";
        document.getElementById('statusvalue').innerHTML = "OK";
        document.getElementById("stats").removeAttribute("fault");
    }
}

function generateSvg(data) {

 var d = new Date();
 var day;
 var x, y, d, o, m, s, e, dt;
 var sums = {};
 var detail;

 var html = `
 <svg class="svg" version="1.1" height="100%"
    viewbox="0 0 3050 314"
     xmlns="http://www.w3.org/2000/svg">

  <g>
 `;

 for (x=3000; x>=0; x-= 50) {
   day = d.getDate();
   d.setDate(d.getDate() - 1);
   html += `
      <line class="timeline" x1="${x}" x2="${x}" y1="14" y2="302"  />
      <text class="serieslabel" x="${x}" y="312" >${day}</text>
   `;
 }

 for (e of data) {
 // Each entry: days_ago, YY, MM, DD, hh, mm, ss, duration, min, avg, max
   dt = new Date(e[1], e[2]-1, e[3], e[4], e[5], e[6]); // python date is 1 based

   x = Math.trunc(3000 + (e[0] * 50));
   y = Math.trunc((288 - (((e[4] * 60) + e[5]) / 5)) + 14); // 288 pixel range
   d = Math.min(Math.max(Math.trunc(e[7] / 5), 5), 50); // Bound between 5 px and 50 px
   o = Math.trunc(((e[10]/ 10) % 1) * 255); // >= 10A is full on

   sums[x] = (sums[x] || 0) + e[7];

   m = padTime(Math.trunc(e[7]/60));
   s = padTime(e[7]%60);

   html += `
      <circle id="${x}_${y}_${d}" class="event" onclick="open_detail('${x}_${y}_${d}', '${dateToString(dt)}', '${timeToString(dt)}', '${m}:${s}', '${e[8]}', '${e[9]}', '${e[10]}')" cx="${x}" cy="${y}" r="${d}" stroke="black" stroke-width="1" fill="rgb(${o},0,0)"/>
   `;
  }

 for (x in sums) {
   m = padTime(Math.trunc(sums[x]/60));
   s = padTime(sums[x]%60);
   html += `
      <text class="serieslabel" x="${x}" y="10" >${m}:${s}</text>
   `;
 }
 html += `
  </g>
  </svg>
 `;

 var g = document.getElementById('timegraph');
 g.innerHTML = html;
 g.scrollLeft = g.scrollWidth;
}

function websocket() {
	var scheme
	scheme = 'ws:';
	var wsUri = scheme + '//' + window.location.hostname;
	websocket = new WebSocket(wsUri);
	websocket.onmessage = function(evt) { onMessage (evt) };
}

function onMessage(evt)	{
    o = JSON.parse(evt.data);

    document.getElementById('currentvalue').innerHTML = Number.parseFloat(o.amps).toFixed(3) + " A";
    document.getElementById('beat').style.display="block"
    setTimeout(function(){document.getElementById('beat').style.display="none"}, 500);

    updateStatus(o.status);
}

function refresh() {
    fetch('/api/getHistoricalData')
        .then(response => response.json())
        .then(data => generateSvg(data));
}

function open_detail(e, detail_date, detail_time, detail_runtime, detail_min, detail_avg, detail_max)
{
    close_detail();
    document.getElementById("stats").style.display="block";
    document.getElementById("stats").setAttribute("event",e);
    document.getElementById("detail_date").innerHTML = detail_date;
    document.getElementById("detail_time").innerHTML = detail_time;
    document.getElementById("detail_runtime").innerHTML = detail_runtime;
    document.getElementById("detail_min").innerHTML = detail_min;
    document.getElementById("detail_avg").innerHTML = detail_avg;
    document.getElementById("detail_max").innerHTML = detail_max;
    document.getElementById(e).style.stroke="red";
    document.getElementById(e).style['stroke-width'] = "8";
}

function close_detail()
{
    e  = document.getElementById("stats").getAttribute("event");
    if (e != null) {
        document.getElementById("stats").style.display="none";
        document.getElementById(e).style.stroke="black";
        document.getElementById(e).style['stroke-width'] = "1";
    }
    document.getElementById("stats").removeAttribute("event");
}

function openConfig() {
    document.getElementById("config_maxRuntime").disabled = true;
    document.getElementById("config_maxCycles").disabled = true;
    document.getElementById("config_minCurrent").disabled = true;
    document.getElementById("config").style.display = "block";

    fetch('/api/getConfig')
        .then(response => (response.json()))
        .then(data => {
            o = JSON.parse(data);
            console.log(o);
             //  YY, MM, DD, hh, mm, ss
            dt = new Date(o.bootTime[0], o.bootTime[1]-1, o.bootTime[2], o.bootTime[3], o.bootTime[4], o.bootTime[5]); // python date is 1 based

            document.getElementById("config_maxRuntime").value = o.maxRuntime;
            document.getElementById("config_maxCycles").value = o.maxCycles;
            document.getElementById("config_minCurrent").value = o.minCurrent;
            document.getElementById("config_maxRuntime").disabled = false;
            document.getElementById("config_maxCycles").disabled = false;
            document.getElementById("config_minCurrent").disabled = false;
            document.getElementById("config_bootTime_value").innerHTML = dateToString(dt) + " " + timeToString(dt);
        });
}

function closeConfig(save) {
    if (save === true) {
        var c = {
            maxRuntime: parseInt(document.getElementById("config_maxRuntime").value),
            maxCycles: parseInt(document.getElementById("config_maxCycles").value),
            minCurrent: parseFloat(document.getElementById("config_minCurrent").value)
        }
        fetch("/api/setConfig", {
            method: "POST",
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(c)
        });
    }
    document.getElementById("config").style.display="none";
}

function toggleFault() {
    document.getElementById("statusvalue").style.backgroundColor = "grey";
    fault =  document.getElementById("stats").hasAttribute("fault");
    fault = !fault;

    var f = {
        fault: fault
    }

    fetch("/api/setFault", {
        method: "POST",
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(f)
    });
}

function factoryReset() {
    if (confirm("This will erase all history!")) {
        setTimeout(function(){reload()}, 3000);
        fetch("/api/reset", {
            method: "PUT",
            headers: {
                'Content-Type': 'application/json'
            },
            body: {}
        });
    }
}
