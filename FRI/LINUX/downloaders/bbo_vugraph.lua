-- BBO vugraph archives (recent)
-- Script author: Piotr Beling <qwak82@gmail.com>

local content = url.download_check("http://www.bridgebase.com/vugraph_archives/vugraph_archives.php")

function clean_html(str)
	str = string.gsub(str, '<br>', ' ')
	return string.gsub(str, '<.->', '')
end

function c(str1, str2)
	if str1=="" then return str2; end
	if str2=="" then return str1; end
	return str1..' | '..str2;
end

for u, n1, n2, n3, n4, n5 in string.gmatch(content,
 '<tr.-<a href="([^"]-)">Download</a>.-<td>(.-)</td>.-<td>(.-)</td>.-<td>(.-)</td>.-<td>(.-)</td>.-<td>(.-)</td>.-</tr>'
) do
        table.insert(results, {["url"]=u, ["format"]="lin", ["name"]=clean_html(c(c(c(n1, n2), c(n3, n4)), n5))})
end

