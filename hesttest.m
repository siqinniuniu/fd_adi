function [ret, spots] = hesttest()
format short

spots = [1.42108547e-14,   5.96831511e+00,   1.16552802e+01,...
         1.70779112e+01,   2.22524330e+01,   2.71943280e+01,...
         3.191838e+01,   3.64387325e+01,   4.07689019e+01,...
         4.49218473e+01,   4.89099946e+01,   5.27452768e+01,...
         5.64391692e+01,   6.00027243e+01,   6.34466044e+01,...
         6.67811141e+01,   7.00162302e+01,   7.31616327e+01,...
         7.62267327e+01,   7.92207012e+01,   8.21524965e+01,...
         8.50308907e+01,   8.78644962e+01,   9.06617914e+01,...
         9.34311459e+01,   9.61808459e+01,   9.89191187e+01,...
         1.00e+02,   1.04394145e+02,   1.07147281e+02,...
         1.09921802e+02,   1.12726010e+02,   1.15568295e+02,...
         1.18457161e+02,   1.21401253e+02,   1.24409379e+02,...
         1.27490539e+02,   1.30653953e+02,   1.33909087e+02,...
         1.37265679e+02,   1.40733772e+02,   1.44323745e+02,...
         1.48046337e+02,   1.51912687e+02,   1.55934365e+02,...
         1.60123402e+02,   1.64492333e+02,   1.69054230e+02,...
         1.73822742e+02,   1.78812138e+02,   1.84037346e+02,...
         1.89514000e+02,   1.95258487e+02,   2.01287994e+02,...
         2.07620563e+02,   2.14275140e+02,   2.21271638e+02,...
         2.28630990e+02,   2.36375215e+02,   2.44527486e+02,...
         2.53112194e+02,   2.62155025e+02,   2.71683036e+02,...
         2.81724736e+02,   2.92310171e+02,   3.03471012e+02,...
         3.15240654e+02,   3.27654312e+02,   3.40749130e+02,...
         3.54564287e+02,   3.69141121e+02,   3.84523245e+02,...
         4.00756684e+02,   4.17890010e+02,   4.35974488e+02,...
         4.55064227e+02,   4.75216345e+02,   4.96491139e+02,...
         5.18952265e+02,   5.42666928e+02,   5.67706085e+02,...
         5.94144653e+02,   6.22061741e+02,   6.51540877e+02,...
         6.82670265e+02,   7.15543048e+02,   7.50257582e+02,...
         7.86917737e+02,   8.25633202e+02,   8.66519817e+02,...
         9.09699918e+02,   9.55302703e+02,   1.00346462e+03,...
         1.05432977e+03,   1.10805035e+03,   1.16478709e+03,...
         1.22470976e+03,   1.28799764e+03,   1.35484011e+03,...
         1.42543715e+03]
% spots = [spots(1)];
spots = spots(spots > 20);
k = 100;
vol = 0.2;
r = 0.06;
t = 0.01;
kappa = 1;
theta = 0.04;
sigma = 0.001;
rho = 0;

% ret = zeros(size(spots));
for i=1:length(spots)
    ret(i) = cosmethodjohnedit(spots(i), k, r ,vol, t, kappa, theta, sigma, rho);
end
% for i=1:length(spots)
    % printf(" %f", ret(i,1));
% end
plot(spots, ret - max(0, (spots-k)));
plot(spots, ret);
% ret
end