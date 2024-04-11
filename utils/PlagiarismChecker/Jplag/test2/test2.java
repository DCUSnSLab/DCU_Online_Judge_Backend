public class test2 {

    public static void main(String[] args) {

        int[] data = { 44, 54, 3, 8, 62, 1, 55, 56 };
        int temp2;
        int cnt = 0;

        for(int m=0; m<data.length; m++) {
            System.out.print(data[m] + ", ");

        }

        for(int i=data.length; i>0; i--) {
            for (int j=0; j<i-1; j++) {
                cnt++;
                if(data[j] > data[j+1]) {
                    temp2 = data[j];
                    data[j] = data[j+1];
                    data[j+1] = temp2;
                }
            }
        }

        for(int k=0; k<data.length; k++) {
            System.out.print(data[k] + ", ");

        }
        System.out.println("\n\n 총 회전 수 : " + cnt);
    }
}
