-- PZBS ostatnio dodane wyniki
-- Script author: Piotr Beling <qwak82@gmail.com>

local pzbs_url = 'http://www.pzbs.pl'
local content = url.download_check(pzbs_url..'/wyn')

for u, n, d in string.gmatch(content,
	'<a href="(/wyn/.-)">%s-([^%s].-)</a>%s-</td>%s-<td>%s-([^%s].-)%s+</td>'
) do
	table.insert(results, {["url"]=pzbs_url..u, ["name"]=n..' ('..d..')'})
end

