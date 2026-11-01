* Reproduces Table 1 and Table 2. Stata 17 or later.
clear all
set more off
cd "C:\Users\author\Dropbox\AI_adoption_project"
use "data/panel.dta", clear

* Table 1
quietly summarize roa
local n_obs = r(N)
local mean_roa = r(mean)
quietly summarize adopted
local share_adopted = r(mean)
egen firm_tag = tag(firm)
quietly count if firm_tag
local n_firms = r(N)
drop firm_tag
file open fh using "output/table1.csv", write replace
file write fh "statistic,value" _n
file write fh "n_obs,`n_obs'.000000" _n
file write fh "n_firms,`n_firms'.000000" _n
file write fh "mean_roa," %9.6f (`mean_roa') _n
file write fh "share_adopted," %9.6f (`share_adopted') _n
file close fh

* Table 2
regress roa adopted size age i.year
matrix b = e(b)'
clear
svmat b, names(estimate)
gen term = ""
replace term = "adopted" in 1
replace term = "size" in 2
replace term = "age" in 3
replace term = "year_2018" in 4
replace term = "year_2019" in 5
replace term = "year_2020" in 6
replace term = "year_2021" in 7
replace term = "year_2022" in 8
replace term = "const" in 9
drop if term == "year_2018"
rename estimate1 estimate
format estimate %12.6f
order term estimate
export delimited using "output/table2.csv", replace
